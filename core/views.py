import google.generativeai as genai
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Count
from django.utils import timezone
from django.http import HttpResponse, JsonResponse
from django.core.management import call_command
from datetime import datetime
import os

from .models import Room, Booking, Destination, Review

# --- CẤU HÌNH HỖ TRỢ ---
def is_admin(user):
    return user.is_authenticated and user.is_staff

# --- 1. HỆ THỐNG AI (GEMINI) ---
def ai_assistant(request):
    user_message = request.GET.get('message', '')
    
    if user_message:
        # Lấy Key từ Environment Variables trên Render
        api_key = os.environ.get('GOOGLE_API_KEY')
        
        if not api_key:
            return JsonResponse({'reply': "Hệ thống chưa cấu hình API Key. Vui lòng kiểm tra Render!"})

        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Lấy dữ liệu thực tế từ Database để "dạy" cho AI
            available_rooms = Room.objects.filter(is_available=True)[:5]
            room_list = ", ".join([f"Phòng {r.room_number} tại {r.address} (Giá: {r.price} VNĐ)" for r in available_rooms])
            
            # Ngữ cảnh nâng cao giúp AI trả lời dựa trên dữ liệu thật của khách sạn
            context = (
                f"Bạn là trợ lý ảo thông minh của khách sạn MyHotel. "
                f"Danh sách phòng hiện có: {room_list if room_list else 'Hiện tại hết phòng'}. "
                f"Hãy trả lời khách hàng bằng tiếng Việt, lịch sự, ngắn gọn và tập trung vào thông tin khách sạn. "
                f"Câu hỏi của khách: {user_message}"
            )
            
            response = model.generate_content(context)
            return JsonResponse({'reply': response.text})
            
        except Exception as e:
            print(f"--- LỖI AI THỰC TẾ: {str(e)} ---")
            return JsonResponse({'reply': "Xin lỗi, mình đang bận một chút. Bạn thử lại sau nhé!"})
            
    return JsonResponse({'reply': "Bạn muốn hỏi gì về MyHotel ạ?"})

# --- 2. TRANG CHỦ & CHI TIẾT ---
def home(request):
    query = request.GET.get('q', '')
    if query:
        rooms = Room.objects.filter(
            Q(room_number__icontains=query) |
            Q(address__icontains=query) |
            Q(description__icontains=query),
            is_available=True
        ).distinct()
    else:
        rooms = Room.objects.filter(is_available=True)

    destinations = Destination.objects.all()
    return render(request, 'core/home.html', {
        'rooms': rooms,
        'destinations': destinations,
        'query': query
    })

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
                    messages.error(request, "Ngày trả phải sau ngày nhận phòng.")
                elif check_in < timezone.now().date():
                    messages.error(request, "Không thể đặt ngày trong quá khứ.")
                else:
                    Booking.objects.create(
                        user=request.user, room=room,
                        check_in=check_in, check_out=check_out, status='pending'
                    )
                    messages.success(request, f"Đã gửi yêu cầu đặt phòng {room.room_number}!")
                    return redirect('my_bookings')
            except (ValueError, TypeError):
                messages.error(request, "Vui lòng chọn đầy đủ ngày tháng.")

        elif 'submit_review' in request.POST:
            rating = request.POST.get('rating')
            comment = request.POST.get('comment')
            if rating and comment:
                Review.objects.create(
                    room=room, user=request.user,
                    rating=int(rating), comment=comment
                )
                messages.success(request, "Cảm ơn bạn đã đánh giá!")
                return redirect('room_detail', pk=pk)

    return render(request, 'core/room_detail.html', {'room': room, 'reviews': reviews})

# --- 3. QUẢN LÝ DÀNH CHO KHÁCH ---
@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'core/my_bookings.html', {'bookings': bookings})

@login_required
def cancel_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    if booking.status == 'pending':
        booking.delete()
        messages.success(request, "Đã hủy đơn đặt phòng.")
    else:
        messages.error(request, "Không thể hủy đơn đã được xử lý.")
    return redirect('my_bookings')

# --- 4. QUẢN LÝ DÀNH CHO ADMIN ---
@user_passes_test(is_admin)
def admin_dashboard(request):
    booking_stats = Booking.objects.values('status').annotate(total=Count('id'))
    room_stats = Room.objects.values('address').annotate(total=Count('id'))
    pending_bookings = Booking.objects.filter(status='pending').order_by('-created_at')

    return render(request, 'core/dashboard.html', {
        'booking_labels': [item['status'].capitalize() for item in booking_stats],
        'booking_data': [item['total'] for item in booking_stats],
        'room_labels': [item['address'] for item in room_stats],
        'room_data': [item['total'] for item in room_stats],
        'pending_bookings': pending_bookings
    })

@user_passes_test(is_admin)
def manage_booking(request, pk, action):
    booking = get_object_or_404(Booking, pk=pk)
    if action == 'approve':
        booking.status = 'approved'
        messages.success(request, f"Đã duyệt đơn của {booking.user.username}")
    elif action == 'reject':
        booking.status = 'rejected'
        messages.warning(request, f"Đã từ chối đơn của {booking.user.username}")
    booking.save()
    return redirect('admin_dashboard')

# --- 5. CÀI ĐẶT HỆ THỐNG ---
def setup_database(request):
    call_command('migrate')
    if not User.objects.filter(username='admin_moi').exists():
        User.objects.create_superuser('admin_moi', 'admin@example.com', 'matkhau123')
        return HttpResponse("Khởi tạo hệ thống thành công! Tài khoản: admin_moi / mật khẩu: matkhau123")
    return HttpResponse("Hệ thống đã hoạt động bình thường.")