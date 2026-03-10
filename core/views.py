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
    Xử lý Chatbot sử dụng Gemini 1.5 Flash.
    """
    user_message = request.GET.get('message', '').strip()
    
    if not user_message:
        return JsonResponse({'reply': "Chào bạn! MyHotel có thể giúp gì cho bạn ạ?"})

    api_key = os.environ.get('GOOGLE_API_KEY')
    if not api_key:
        return JsonResponse({'reply': "Chatbot đang bảo trì hệ thống API, vui lòng thử lại sau."})

    try:
        genai.configure(api_key=api_key.strip())
        
        # Sử dụng model Flash cho tốc độ phản hồi nhanh nhất
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Lấy tối đa 3 phòng trống để làm ngữ cảnh (Context)
        rooms = Room.objects.filter(is_available=True)[:3]
        if rooms.exists():
            room_list = [f"Phòng {r.room_number} tại {r.address} giá {r.price} VNĐ" for r in rooms]
            context_rooms = "Các phòng còn trống: " + ", ".join(room_list)
        else:
            context_rooms = "Hiện tại khách sạn đã hết phòng trống."

        prompt = (
            f"Bạn là 'Trợ lý ảo MyHotel'. {context_rooms}. "
            f"Hãy trả lời khách hàng bằng tiếng Việt, lịch sự, ngắn gọn dưới 50 từ. "
            f"Nếu khách hỏi về phòng, hãy ưu tiên thông tin trên. "
            f"Khách hỏi: {user_message}"
        )
        
        response = model.generate_content(prompt)
        
        if response and response.text:
            return JsonResponse({'reply': response.text.strip()})
        return JsonResponse({'reply': "Xin lỗi, mình chưa hiểu ý bạn. Bạn có thể hỏi rõ hơn không?"})
        
    except Exception as e:
        print(f"--- AI ERROR: {str(e)} ---")
        return JsonResponse({'reply': "Mình hơi mệt một chút, bạn nhắn lại sau ít phút nhé!"})

# --- 2. TRANG CHỦ & TÌM KIẾM ---
def home(request):
    query = request.GET.get('q', '').strip()
    destinations = Destination.objects.all()
    # Hiển thị tất cả phòng nhưng đánh dấu trạng thái
    rooms_available = Room.objects.all().order_by('-is_available')
    
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
                messages.warning(request, "Vui lòng đăng nhập để thực hiện đặt phòng.")
                return redirect('login')

            check_in_str = request.POST.get('check_in')
            check_out_str = request.POST.get('check_out')

            try:
                check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
                check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()

                if check_out <= check_in:
                    messages.error(request, "Ngày trả phòng phải sau ngày nhận phòng.")
                elif check_in < timezone.now().date():
                    messages.error(request, "Không thể đặt phòng cho ngày đã qua.")
                elif not room.is_available:
                    messages.error(request, "Rất tiếc, phòng này vừa mới có người đặt.")
                else:
                    Booking.objects.create(
                        user=request.user, room=room,
                        check_in=check_in, check_out=check_out, status='pending'
                    )
                    messages.success(request, f"Đã gửi yêu cầu đặt phòng {room.room_number}. Vui lòng chờ quản trị viên duyệt!")
                    return redirect('my_bookings')
            except (ValueError, TypeError):
                messages.error(request, "Định dạng ngày tháng không hợp lệ.")

        elif 'submit_review' in request.POST:
            if not request.user.is_authenticated:
                return redirect('login')
            rating = request.POST.get('rating')
            comment = request.POST.get('comment')
            if rating and comment:
                Review.objects.create(room=room, user=request.user, rating=int(rating), comment=comment)
                messages.success(request, "Cảm ơn bạn đã để lại đánh giá!")
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
        messages.error(request, "Đơn hàng đã được xử lý, không thể tự hủy.")
    return redirect('my_bookings')

# --- 5. HỆ THỐNG QUẢN TRỊ (ADMIN DASHBOARD) ---
@user_passes_test(is_admin)
def admin_dashboard(request):
    booking_stats = Booking.objects.values('status').annotate(total=Count('id'))
    room_stats = Room.objects.values('address').annotate(total=Count('id'))
    pending_bookings = Booking.objects.filter(status='pending').order_by('-created_at')

    context = {
        'booking_labels': [item['status'].capitalize() for item in booking_stats],
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
        booking.room.is_available = False # Tự động khóa phòng khi duyệt
        booking.room.save()
        messages.success(request, f"Đã duyệt đơn đặt phòng {booking.room.room_number}.")
    elif action == 'reject':
        booking.status = 'rejected'
        booking.room.is_available = True # Mở lại phòng nếu từ chối
        booking.room.save()
        messages.warning(request, f"Đã từ chối đơn của khách hàng {booking.user.username}.")
    
    booking.save()
    return redirect('admin_dashboard')

# --- 6. KHỞI TẠO CƠ SỞ DỮ LIỆU ---
def setup_database(request):
    """Đồng bộ database và tạo Admin nhanh"""
    try:
        call_command('migrate')
        if not User.objects.filter(username='admin_render').exists():
            User.objects.create_superuser('admin_render', 'admin@hotel.com', 'matkhau123')
            return HttpResponse("Tạo Admin thành công! User: admin_render | Pass: matkhau123")
        return HttpResponse("Hệ thống đã đồng bộ dữ liệu PostgreSQL.")
    except Exception as e:
        return HttpResponse(f"Lỗi khởi tạo: {str(e)}")