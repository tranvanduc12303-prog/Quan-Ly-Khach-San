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
        # Ưu tiên lấy Key từ biến môi trường (Render), nếu không có thì lấy Key dán trực tiếp
        api_key = os.environ.get('GOOGLE_API_KEY', "AIzaSyDKdORffma82ggba_RtbuUMJu1Vc2Nt2UE")
        
        try:
            genai.configure(api_key=api_key)
            model = genai.GenerativeModel('gemini-1.5-flash')
            
            # Ngữ cảnh nâng cao giúp AI trả lời chuyên nghiệp hơn
            prompt = (
                f"Bạn là trợ lý ảo của khách sạn MyHotel. Hãy trả lời thân thiện, "
                f"lịch sự và ngắn gọn câu hỏi sau bằng tiếng Việt: {user_message}"
            )
            
            response = model.generate_content(prompt)
            return JsonResponse({'reply': response.text})
            
        except Exception as e:
            # Dòng này sẽ in lỗi thực tế ra Terminal để bạn dễ sửa
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
        # Xử lý đặt phòng
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
                        user=request.user,
                        room=room,
                        check_in=check_in,
                        check_out=check_out,
                        status='pending'
                    )
                    messages.success(request, f"Đã gửi yêu cầu đặt phòng {room.room_number}!")
                    return redirect('my_bookings')
            except (ValueError, TypeError):
                messages.error(request, "Vui lòng chọn đầy đủ ngày tháng.")

        # Xử lý gửi đánh giá
        elif 'submit_review' in request.POST:
            if not request.user.is_authenticated:
                messages.warning(request, "Đăng nhập để đánh giá.")
                return redirect('login')

            rating = request.POST.get('rating')
            comment = request.POST.get('comment')
            if rating and comment:
                Review.objects.create(
                    room=room,
                    user=request.user,
                    rating=int(rating),
                    comment=comment
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
    booking_labels = [item['status'].capitalize() for item in booking_stats]
    booking_data = [item['total'] for item in booking_stats]

    room_stats = Room.objects.values('address').annotate(total=Count('id'))
    room_labels = [item['address'] for item in room_stats]
    room_data = [item['total'] for item in room_stats]

    pending_bookings = Booking.objects.filter(status='pending').order_by('-created_at')

    return render(request, 'core/dashboard.html', {
        'booking_labels': booking_labels,
        'booking_data': booking_data,
        'room_labels': room_labels,
        'room_data': room_data,
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