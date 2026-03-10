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
    Sửa lỗi 404 model name và tối ưu hóa việc đọc dữ liệu từ Postgres.
    """
    user_message = request.GET.get('message', '').strip()
    
    if not user_message:
        return JsonResponse({'reply': "Chào bạn! MyHotel có thể giúp gì cho bạn ạ?"})

    api_key = os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        return JsonResponse({'reply': "Chatbot chưa được cấu hình API Key trên Render."})

    try:
        # Làm sạch Key để tránh lỗi khoảng trắng
        genai.configure(api_key=api_key.strip())
        
        generation_config = {
            "temperature": 0.7,
            "top_p": 0.95,
            "max_output_tokens": 150,
        }
        
        # Thử tên model chuẩn nhất (dứt điểm lỗi 404)
        model = None
        for m_name in ["gemini-1.5-flash", "models/gemini-1.5-flash"]:
            try:
                model = genai.GenerativeModel(model_name=m_name, generation_config=generation_config)
                break 
            except Exception:
                continue

        if not model:
            raise Exception("Không kết nối được với Gemini.")

        # Lấy dữ liệu thực thực tế từ PostgreSQL
        rooms = Room.objects.filter(is_available=True)[:5]
        context_rooms = "Hiện tại khách sạn đang hết phòng trống."
        if rooms.exists():
            room_data = [f"Phòng {r.room_number} ({r.address}) giá {r.price}VNĐ" for r in rooms]
            context_rooms = "Danh sách phòng còn trống: " + "; ".join(room_data)

        prompt = (
            f"Bạn là 'Trợ lý ảo MyHotel'. Dữ liệu khách sạn: {context_rooms}. "
            f"Trả lời khách bằng tiếng Việt, thân thiện, ngắn gọn (tối đa 2 câu). "
            f"Câu hỏi: {user_message}"
        )
        
        response = model.generate_content(prompt)
        
        if response and response.text:
            return JsonResponse({'reply': response.text})
        return JsonResponse({'reply': "Mình đang xử lý, bạn hỏi lại nhé!"})
        
    except Exception as e:
        print(f"--- AI ERROR: {str(e)} ---")
        return JsonResponse({'reply': "Hệ thống AI đang khởi động lại trên server mới, bạn thử lại sau ít phút nhé!"})

# --- 2. TRANG CHỦ & TÌM KIẾM ---
def home(request):
    query = request.GET.get('q', '').strip()
    destinations = Destination.objects.all()
    # Chỉ lấy phòng còn trống
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
                messages.warning(request, "Bạn cần đăng nhập để đặt phòng.")
                return redirect('login')

            check_in_str = request.POST.get('check_in')
            check_out_str = request.POST.get('check_out')

            try:
                check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
                check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()

                if check_out <= check_in:
                    messages.error(request, "Ngày trả phải sau ngày nhận.")
                elif check_in < timezone.now().date():
                    messages.error(request, "Không thể đặt ngày trong quá khứ.")
                else:
                    Booking.objects.create(
                        user=request.user, room=room,
                        check_in=check_in, check_out=check_out, status='pending'
                    )
                    messages.success(request, f"Yêu cầu đặt phòng {room.room_number} đã được gửi!")
                    return redirect('my_bookings')
            except (ValueError, TypeError):
                messages.error(request, "Vui lòng nhập ngày hợp lệ.")

        elif 'submit_review' in request.POST:
            rating = request.POST.get('rating')
            comment = request.POST.get('comment')
            if rating and comment:
                Review.objects.create(room=room, user=request.user, rating=int(rating), comment=comment)
                messages.success(request, "Cảm ơn bạn đã đánh giá!")
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
        messages.success(request, "Đã hủy yêu cầu.")
    else:
        messages.error(request, "Phòng đã duyệt không thể tự hủy.")
    return redirect('my_bookings')

# --- 5. HỆ THỐNG QUẢN TRỊ (ADMIN DASHBOARD) ---
@user_passes_test(is_admin)
def admin_dashboard(request):
    # Thống kê đơn hàng và phòng từ PostgreSQL
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
    return render(request, 'core/dashboard.html', context)

@user_passes_test(is_admin)
def manage_booking(request, pk, action):
    booking = get_object_or_404(Booking, pk=pk)
    if action == 'approve':
        booking.status = 'approved'
        booking.room.is_available = False
        booking.room.save()
        messages.success(request, f"Đã duyệt phòng {booking.room.room_number}.")
    elif action == 'reject':
        booking.status = 'rejected'
        messages.warning(request, f"Đã từ chối đơn của {booking.user.username}.")
    booking.save()
    return redirect('admin_dashboard')

# --- 6. KHỞI TẠO CƠ SỞ DỮ LIỆU ---
def setup_database(request):
    """Lệnh tạo bảng duy nhất trên PostgreSQL vĩnh viễn"""
    try:
        call_command('migrate')
        if not User.objects.filter(username='admin_moi').exists():
            User.objects.create_superuser('admin_moi', 'admin@example.com', 'matkhau123')
            return HttpResponse("Khởi tạo Admin trên Postgres thành công! User: admin_moi / Pass: matkhau123")
        return HttpResponse("Cơ sở dữ liệu PostgreSQL đã sẵn sàng và đồng bộ.")
    except Exception as e:
        return HttpResponse(f"Lỗi: {str(e)}")