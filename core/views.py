import os
from groq import Groq
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.core.management import call_command

from .models import Room, Booking, Destination, Review, RoomType, Service

# --- TRÌNH BẢO VỆ PHÂN QUYỀN ---
def is_admin(user):
    """Kiểm tra xem người dùng có phải là Admin/Lễ tân không"""
    return user.is_authenticated and user.is_staff

# --- 1. TRANG CHỦ & TÌM KIẾM ---
def home(request):
    """Trang chủ hiển thị danh sách phòng và tìm kiếm nâng cao"""
    query = request.GET.get('q', '').strip()
    destinations = Destination.objects.all()
    rooms = Room.objects.select_related('room_type').all().order_by('-is_available', 'price')
    
    if query:
        rooms = rooms.filter(
            Q(room_number__icontains=query) | 
            Q(address__icontains=query) |
            Q(room_type__name__icontains=query)
        ).distinct()
    return render(request, 'core/home.html', {
        'rooms': rooms, 
        'destinations': destinations, 
        'query': query
    })

# --- 2. CHI TIẾT PHÒNG, ĐẶT PHÒNG & ĐÁNH GIÁ ---
def room_detail(request, pk):
    """Xử lý xem phòng, gửi đơn đặt phòng và viết nhận xét"""
    room = get_object_or_404(Room, pk=pk)
    reviews = room.reviews.select_related('user').order_by('-created_at')
    services = Service.objects.all()

    if request.method == 'POST':
        # Hành động: ĐẶT PHÒNG
        if 'book_room' in request.POST:
            if not request.user.is_authenticated:
                messages.warning(request, "Vui lòng đăng nhập để đặt phòng.")
                return redirect('login')
            
            try:
                check_in = datetime.strptime(request.POST.get('check_in'), '%Y-%m-%d').date()
                check_out = datetime.strptime(request.POST.get('check_out'), '%Y-%m-%d').date()

                if check_out <= check_in:
                    messages.error(request, "Ngày trả phòng phải sau ngày nhận phòng.")
                else:
                    booking = Booking.objects.create(
                        user=request.user, room=room, 
                        check_in=check_in, check_out=check_out, 
                        status='pending'
                    )
                    booking.services.set(request.POST.getlist('services'))
                    messages.success(request, f"Đã gửi yêu cầu đặt phòng {room.room_number}!")
                    return redirect('payment_page', booking_id=booking.id)
            except Exception:
                messages.error(request, "Lỗi xử lý ngày tháng. Vui lòng thử lại.")

        # Hành động: GỬI ĐÁNH GIÁ
        elif 'submit_review' in request.POST:
            if not request.user.is_authenticated:
                messages.error(request, "Bạn cần đăng nhập để đánh giá.")
            else:
                Review.objects.create(
                    room=room, user=request.user,
                    rating=int(request.POST.get('rating', 5)),
                    comment=request.POST.get('comment', '')
                )
                messages.success(request, "Cảm ơn đóng góp của bạn!")
                return redirect('room_detail', pk=pk)

    return render(request, 'core/room_detail.html', {
        'room': room, 'reviews': reviews, 'services': services
    })

# --- 3. QUẢN TRỊ VIÊN (DASHBOARD & BIỂU ĐỒ) ---
@user_passes_test(is_admin)
def admin_dashboard(request):
    """Thống kê doanh thu và dữ liệu cho Chart.js"""
    total_revenue = Booking.objects.filter(Q(status='approved') | Q(status='completed')).aggregate(total=Sum('room__price'))['total'] or 0
    pending_bookings = Booking.objects.filter(status='pending').select_related('user', 'room')
    
    # Dữ liệu biểu đồ Trạng thái
    status_stats = Booking.objects.values('status').annotate(total=Count('id'))
    # Dữ liệu biểu đồ Khu vực
    room_stats = Room.objects.values('address').annotate(total=Count('id'))

    context = {
        'total_revenue': total_revenue,
        'pending_bookings': pending_bookings,
        'pending_count': pending_bookings.count(),
        'room_count': Room.objects.count(),
        'booking_labels': [s['status'].capitalize() for s in status_stats],
        'booking_data': [s['total'] for s in status_stats],
        'room_labels': [r['address'] for r in room_stats],
        'room_data': [r['total'] for r in room_stats],
    }
    return render(request, 'core/dashboard.html', context)

@user_passes_test(is_admin)
def manage_booking(request, pk, action):
    """Duyệt hoặc từ chối đơn hàng từ Admin"""
    booking = get_object_or_404(Booking, pk=pk)
    if action == 'approve':
        booking.status, booking.room.is_available = 'approved', False
    elif action == 'reject':
        booking.status, booking.room.is_available = 'rejected', True
    booking.room.save()
    booking.save()
    messages.success(request, f"Đã cập nhật đơn hàng #{booking.id}")
    return redirect('admin_dashboard')

# --- 4. THANH TOÁN & KHÁCH HÀNG ---
@login_required
def payment_page(request, booking_id):
    """Trang hiển thị mã QR thanh toán"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    # Tạo URL VietQR (Thay số tài khoản của bạn ở đây)
    qr_url = f"https://img.vietqr.io/image/MB-0987654321-compact2.png?amount={int(booking.room.price)}&addInfo=MYHOTEL{booking.id}&accountName=MYHOTEL"
    return render(request, 'core/payment.html', {'booking': booking, 'qr_url': qr_url})

@login_required
def my_bookings(request):
    """Xem danh sách phòng đã đặt của tôi"""
    bookings = Booking.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'core/my_bookings.html', {'bookings': bookings})

# --- 5. AI ASSISTANT ---
def ai_assistant(request):
    """Chatbot AI tư vấn phòng dựa trên Groq"""
    user_message = request.GET.get('message', '').strip()
    if not user_message:
        return JsonResponse({'reply': "Chào bạn! Mình có thể giúp gì?"})

    api_key = os.environ.get('GROQ_API_KEY')
    if not api_key:
        return JsonResponse({'reply': "Hệ thống AI chưa được cấu hình API Key."})

    try:
        client = Groq(api_key=api_key.strip())
        available_rooms = Room.objects.filter(is_available=True)[:3]
        room_info = ", ".join([f"Phòng {r.room_number} giá {int(r.price):,} VNĐ" for r in available_rooms])
        
        prompt = f"Bạn là lễ tân MyHotel. Dữ liệu phòng trống: {room_info}. Hãy trả lời: {user_message}"
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192",
            temperature=0.7,
        )
        return JsonResponse({'reply': completion.choices[0].message.content.strip()})
    except Exception:
        return JsonResponse({'reply': "Chatbot hiện đang bảo trì."})

# --- 6. HỆ THỐNG ---
def setup_database(request):
    """Chạy lệnh khởi tạo dữ liệu trên Render"""
    try:
        call_command('migrate')
        if not User.objects.filter(username='admin_moi').exists():
            User.objects.create_superuser('admin_moi', 'admin@hotel.com', 'admin12345')
        return HttpResponse("Setup thành công! Tài khoản: admin_moi / mật khẩu: admin12345")
    except Exception as e:
        return HttpResponse(f"Lỗi: {e}")