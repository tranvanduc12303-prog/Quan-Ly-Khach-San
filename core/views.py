import os
import google.generativeai as genai
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.core.management import call_command

from .models import Room, Booking, Destination, Review

# --- CẤU HÌNH HỖ TRỢ ---
def is_admin(user):
    return user.is_authenticated and user.is_staff

# --- 1. HỆ THỐNG AI (GEMINI) ---
def ai_assistant(request):
    """
    Xử lý tin nhắn từ chatbot sử dụng Gemini API.
    Sửa lỗi 404 bằng cách sử dụng tên model trực tiếp: 'gemini-1.5-flash'.
    """
    user_message = request.GET.get('message', '').strip()
    
    if not user_message:
        return JsonResponse({'reply': "Chào bạn! MyHotel có thể giúp gì cho bạn ạ?"})

    # Lấy API Key từ Environment trên Render
    api_key = os.environ.get('GOOGLE_API_KEY')
    if not api_key or len(api_key) < 10:
        return JsonResponse({'reply': "Chatbot chưa được cấu hình API Key chính xác trên Render."})

    try:
        genai.configure(api_key=api_key)
        
        # Cấu hình tham số phản hồi
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 150,
        }
        
        # FIX: Sử dụng tên model chuẩn để tránh lỗi 404 models/gemini-1.5-flash
        model = genai.GenerativeModel(
            model_name="gemini-1.5-flash", 
            generation_config=generation_config
        )
        
        # Lấy dữ liệu thực tế để cung cấp ngữ cảnh cho AI (RAG đơn giản)
        rooms = Room.objects.filter(is_available=True)[:5]
        if rooms.exists():
            room_data = [f"Phòng {r.room_number} tại {r.address} giá {r.price}VNĐ" for r in rooms]
            context_rooms = "Danh sách phòng trống hiện có: " + "; ".join(room_data)
        else:
            context_rooms = "Hiện tại khách sạn đang hết phòng trống."

        prompt = (
            f"Bạn là 'Trợ lý ảo MyHotel'. Dữ liệu khách sạn: {context_rooms}. "
            f"Hãy trả lời khách bằng tiếng Việt, lịch sự, ngắn gọn (tối đa 2 câu). "
            f"Câu hỏi: {user_message}"
        )
        
        response = model.generate_content(prompt)
        
        if response and response.text:
            return JsonResponse({'reply': response.text})
        return JsonResponse({'reply': "Mình đang suy nghĩ, bạn hỏi lại câu khác nhé!"})
        
    except Exception as e:
        # Ghi log lỗi chi tiết để debug trên Render
        print(f"--- CRITICAL AI ERROR: {str(e)} ---")
        return JsonResponse({'reply': "Hệ thống AI đang bận (lỗi kết nối), bạn thử lại sau nhé!"})

# --- 2. TRANG CHỦ & TÌM KIẾM ---
def home(request):
    query = request.GET.get('q', '').strip()
    destinations = Destination.objects.all()
    rooms_available = Room.objects.filter(is_available=True)
    
    if query:
        rooms = rooms_available.filter(
            Q(room_number__icontains=query) |
            Q(address__icontains=query) |
            Q(description__icontains=query)
        ).distinct()
    else:
        rooms = rooms_available

    return render(request, 'core/home.html', {
        'rooms': rooms,
        'destinations': destinations,
        'query': query
    })

# --- 3. CHI TIẾT PHÒNG & ĐẶT PHÒNG ---
def room_detail(request, pk):
    room = get_object_or_404(Room, pk=pk)
    reviews = room.reviews.all().order_by('-created_at')

    if request.method == 'POST':
        if 'book_room' in request.POST:
            if not request.user.is_authenticated:
                messages.warning(request, "Vui lòng đăng nhập để đặt phòng.")
                return redirect('login')

            check_in_str = request.POST.get('check_in')
            check_out_str = request.POST.get('check_out')

            try:
                check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
                check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()

                if check_out <= check_in:
                    messages.error(request, "Ngày trả phòng phải sau ngày nhận phòng.")
                elif check_in < timezone.now().date():
                    messages.error(request, "Không thể đặt phòng cho ngày trong quá khứ.")
                else:
                    Booking.objects.create(
                        user=request.user, room=room,
                        check_in=check_in, check_out=check_out, status='pending'
                    )
                    messages.success(request, f"Đã gửi yêu cầu đặt phòng {room.room_number}!")
                    return redirect('my_bookings')
            except (ValueError, TypeError):
                messages.error(request, "Vui lòng chọn định dạng ngày hợp lệ.")

        elif 'submit_review' in request.POST:
            rating = request.POST.get('rating')
            comment = request.POST.get('comment')
            if rating and comment:
                Review.objects.create(room=room, user=request.user, rating=int(rating), comment=comment)
                messages.success(request, "Cảm ơn bạn đã gửi đánh giá!")
                return redirect('room_detail', pk=pk)

    return render(request, 'core/room_detail.html', {'room': room, 'reviews': reviews})

# --- 4. QUẢN LÝ CHO KHÁCH HÀNG ---
@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'core/my_bookings.html', {'bookings': bookings})

@login_required
def cancel_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    if booking.status == 'pending':
        booking.delete()
        messages.success(request, "Đã hủy yêu cầu đặt phòng thành công.")
    else:
        messages.error(request, "Đơn đã được xử lý, không thể tự hủy.")
    return redirect('my_bookings')

# --- 5. HỆ THỐNG QUẢN TRỊ (ADMIN) ---
@user_passes_test(is_admin)
def admin_dashboard(request):
    """
    Yêu cầu file: core/templates/core/dashboard.html phải tồn tại.
    """
    booking_stats = Booking.objects.values('status').annotate(total=Count('id'))
    room_stats = Room.objects.values('address').annotate(total=Count('id'))
    pending_bookings = Booking.objects.filter(status='pending').order_by('-created_at')

    context = {
        'booking_labels': [item['status'].upper() for item in booking_stats],
        'booking_data': [item['total'] for item in booking_stats],
        'room_labels': [item['address'] for item in room_stats],
        'room_data': [item['total'] for item in room_stats],
        'pending_bookings': pending_bookings
    }
    # Đảm bảo đường dẫn template khớp với core/templates/core/dashboard.html
    return render(request, 'core/dashboard.html', context)

@user_passes_test(is_admin)
def manage_booking(request, pk, action):
    booking = get_object_or_404(Booking, pk=pk)
    if action == 'approve':
        booking.status = 'approved'
        booking.room.is_available = False
        booking.room.save()
        messages.success(request, f"Đã duyệt và khóa phòng {booking.room.room_number}.")
    elif action == 'reject':
        booking.status = 'rejected'
        messages.warning(request, f"Đã từ chối đơn của {booking.user.username}.")
    booking.save()
    return redirect('admin_dashboard')

# --- 6. KHỞI TẠO HỆ THỐNG ---
def setup_database(request):
    try:
        call_command('migrate')
        if not User.objects.filter(username='admin_moi').exists():
            User.objects.create_superuser('admin_moi', 'admin@example.com', 'matkhau123')
            return HttpResponse("Khởi tạo Admin thành công! User: admin_moi / Pass: matkhau123")
        return HttpResponse("Hệ thống cơ sở dữ liệu đã sẵn sàng.")
    except Exception as e:
        return HttpResponse(f"Lỗi khởi tạo: {str(e)}")