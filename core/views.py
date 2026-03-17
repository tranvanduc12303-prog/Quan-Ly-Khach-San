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

# ==========================================
# 1. HỖ TRỢ PHÂN QUYỀN & TIỆN ÍCH
# ==========================================
def is_admin(user):
    """Kiểm tra quyền Admin hoặc Nhân viên lễ tân"""
    return user.is_authenticated and user.is_staff

# ==========================================
# 2. HỆ THỐNG AI TƯ VẤN (SỬ DỤNG GROQ)
# ==========================================
def ai_assistant(request):
    """Chatbot AI hỗ trợ tư vấn dựa trên danh sách phòng trống thực tế"""
    user_message = request.GET.get('message', '').strip()
    if not user_message:
        return JsonResponse({'reply': "Chào bạn! MyHotel có thể giúp gì cho bạn?"})

    api_key = os.environ.get('GROQ_API_KEY')
    if not api_key:
        return JsonResponse({'reply': "Chatbot chưa cấu hình API Key. Vui lòng liên hệ Admin."})

    try:
        client = Groq(api_key=api_key.strip())
        # Cung cấp ngữ cảnh về các phòng trống cho AI
        available_rooms = Room.objects.filter(is_available=True).select_related('room_type')[:3]
        room_info = [f"Phòng {r.room_number} ({r.room_type.name}) giá {int(r.price):,} VNĐ" for r in available_rooms]
        context = "Hiện có các phòng trống: " + ", ".join(room_info) if room_info else "Hiện tại đã hết phòng trống."

        prompt = f"Bạn là lễ tân ảo MyHotel. {context}. Hãy trả lời bằng tiếng Việt lịch sự, ngắn gọn: {user_message}"
        
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192",
            temperature=0.7,
        )
        return JsonResponse({'reply': completion.choices[0].message.content.strip()})
    except Exception as e:
        return JsonResponse({'reply': "Xin lỗi, chatbot đang bận. Bạn vui lòng thử lại sau hoặc gọi hotline nhé!"})

# ==========================================
# 3. TRANG CHỦ & TÌM KIẾM PHÒNG
# ==========================================
def home(request):
    """Trang chủ hiển thị danh sách phòng, lọc theo tìm kiếm và địa điểm"""
    query = request.GET.get('q', '').strip()
    dest_id = request.GET.get('destination')
    
    destinations = Destination.objects.all()
    rooms = Room.objects.select_related('room_type', 'destination').all().order_by('-is_available', 'price')
    
    # Logic tìm kiếm đa điều kiện
    if query:
        rooms = rooms.filter(
            Q(room_number__icontains=query) | 
            Q(address__icontains=query) |
            Q(description__icontains=query) |
            Q(room_type__name__icontains=query)
        ).distinct()
    
    if dest_id:
        rooms = rooms.filter(destination_id=dest_id)

    return render(request, 'core/home.html', {
        'rooms': rooms, 
        'destinations': destinations, 
        'query': query,
        'selected_dest': dest_id
    })

# ==========================================
# 4. CHI TIẾT PHÒNG, ĐẶT PHÒNG & ĐÁNH GIÁ
# ==========================================
def room_detail(request, pk):
    """Xem chi tiết phòng, xử lý đặt phòng và gửi review khách hàng"""
    room = get_object_or_404(Room, pk=pk)
    reviews = room.reviews.select_related('user').order_by('-created_at')
    services = Service.objects.all()
    avg_rating = reviews.aggregate(Avg('rating'))['rating__avg'] or 0

    if request.method == 'POST':
        # --- Hành động: ĐẶT PHÒNG ---
        if 'book_room' in request.POST:
            if not request.user.is_authenticated:
                messages.warning(request, "Vui lòng đăng nhập để đặt phòng.")
                return redirect('login')
            
            try:
                check_in = datetime.strptime(request.POST.get('check_in'), '%Y-%m-%d').date()
                check_out = datetime.strptime(request.POST.get('check_out'), '%Y-%m-%d').date()

                if check_out <= check_in:
                    messages.error(request, "Ngày trả phòng phải sau ngày nhận phòng.")
                elif check_in < timezone.now().date():
                    messages.error(request, "Không thể đặt phòng cho ngày đã qua.")
                else:
                    booking = Booking.objects.create(
                        user=request.user, room=room, 
                        check_in=check_in, check_out=check_out, 
                        status='pending'
                    )
                    # Thêm các dịch vụ khách đã chọn
                    selected_services = request.POST.getlist('services')
                    if selected_services:
                        booking.services.set(selected_services)
                    
                    messages.success(request, "Đặt phòng thành công! Vui lòng hoàn tất thanh toán.")
                    return redirect('payment_page', booking_id=booking.id)
            except ValueError:
                messages.error(request, "Lỗi định dạng ngày tháng.")

        # --- Hành động: GỬI ĐÁNH GIÁ ---
        elif 'submit_review' in request.POST:
            if not request.user.is_authenticated:
                messages.error(request, "Bạn cần đăng nhập để viết đánh giá.")
            else:
                Review.objects.create(
                    room=room, user=request.user,
                    rating=int(request.POST.get('rating', 5)),
                    comment=request.POST.get('comment', '').strip()
                )
                messages.success(request, "Cảm ơn bạn đã đóng góp ý kiến!")
                return redirect('room_detail', pk=pk)

    return render(request, 'core/room_detail.html', {
        'room': room, 
        'reviews': reviews, 
        'services': services,
        'avg_rating': round(avg_rating, 1)
    })

# ==========================================
# 5. QUẢN TRỊ (ADMIN DASHBOARD)
# ==========================================
@user_passes_test(is_admin)
def admin_dashboard(request):
    """Trung tâm điều khiển: Biểu đồ thống kê và quản lý đơn hàng"""
    # 1. Thống kê tổng quan
    total_revenue = Booking.objects.filter(Q(status='approved') | Q(is_paid=True)).aggregate(total=Sum('room__price'))['total'] or 0
    pending_bookings = Booking.objects.filter(status='pending').select_related('user', 'room')
    
    # 2. Dữ liệu BIỂU ĐỒ 1: Trạng thái đơn đặt phòng
    status_stats = Booking.objects.values('status').annotate(total=Count('id'))
    booking_labels = [s['status'].capitalize() for s in status_stats]
    booking_data = [s['total'] for s in status_stats]

    # 3. Dữ liệu BIỂU ĐỒ 2: Phân bổ phòng theo Khu vực
    room_stats = Room.objects.values('address').annotate(total=Count('id'))
    room_labels = [r['address'] for r in room_stats]
    room_data = [r['total'] for r in room_stats]

    context = {
        'total_revenue': total_revenue,
        'pending_bookings': pending_bookings,
        'pending_count': pending_bookings.count(),
        'room_count': Room.objects.count(),
        'user_count': User.objects.count(),
        # Các biến truyền vào JavaScript để vẽ Chart.js
        'booking_labels': booking_labels,
        'booking_data': booking_data,
        'room_labels': room_labels,
        'room_data': room_data,
    }
    return render(request, 'core/dashboard.html', context)

@user_passes_test(is_admin)
def manage_booking(request, pk, action):
    """Duyệt hoặc từ chối đơn đặt phòng của khách"""
    booking = get_object_or_404(Booking, pk=pk)
    if action == 'approve':
        booking.status = 'approved'
        booking.room.is_available = False # Khóa phòng
    elif action == 'reject':
        booking.status = 'rejected'
        booking.room.is_available = True # Mở lại phòng
    elif action == 'complete':
        booking.status = 'completed'
        booking.room.is_available = True
    
    booking.room.save()
    booking.save()
    messages.info(request, f"Đã cập nhật đơn hàng #{booking.id}")
    return redirect('admin_dashboard')

# ==========================================
# 6. THANH TOÁN & TÀI KHOẢN
# ==========================================
@login_required
def payment_page(request, booking_id):
    """Trang thanh toán QR Code VietQR"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    # Cấu hình tài khoản nhận tiền
    BANK_ID, ACCOUNT_NO, ACCOUNT_NAME = "MB", "0987654321", "MYHOTEL ADMIN"
    amount = int(booking.total_price)
    qr_url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-compact2.png?amount={amount}&addInfo=MYHOTEL{booking.id}&accountName={ACCOUNT_NAME}"
    
    return render(request, 'core/payment.html', {'booking': booking, 'qr_url': qr_url})

@login_required
def my_bookings(request):
    """Trang xem lịch sử đặt phòng của khách hàng"""
    bookings = Booking.objects.filter(user=request.user).select_related('room').order_by('-created_at')
    return render(request, 'core/my_bookings.html', {'bookings': bookings})

# ==========================================
# 7. KHỞI TẠO & CẤU HÌNH HỆ THỐNG
# ==========================================
def setup_database(request):
    """Lệnh tự động chạy migrate và tạo admin khi deploy lên Render"""
    try:
        call_command('migrate')
        if not User.objects.filter(username='admin_moi').exists():
            User.objects.create_superuser('admin_moi', 'admin@hotel.com', 'admin12345')
            return HttpResponse("Khởi tạo Admin thành công (admin_moi/admin12345).")
        return HttpResponse("Hệ thống đã sẵn sàng.")
    except Exception as e:
        return HttpResponse(f"Lỗi khi cấu hình: {e}")