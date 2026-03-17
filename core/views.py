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

# --- KIỂM TRA QUYỀN TRUY CẬP ---
def is_admin(user):
    """Kiểm tra quyền Admin hoặc Nhân viên"""
    return user.is_authenticated and user.is_staff

# --- 1. QUẢN LÝ THANH TOÁN (Sửa lỗi 500) ---
@login_required
def payment_page(request, booking_id):
    """Trang hiển thị mã QR thanh toán VietQR và thông tin hóa đơn"""
    # Lấy đơn đặt phòng, đảm bảo đúng người dùng sở hữu đơn đó
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    # Cấu hình tài khoản nhận tiền (Bạn có thể thay đổi số tài khoản ở đây)
    BANK_ID = "MB"  # Ngân hàng MB Bank
    ACCOUNT_NO = "0987654321" 
    ACCOUNT_NAME = "KHACH SAN MYHOTEL"
    
    # Tính tổng tiền (Giá phòng + Dịch vụ nếu có)
    total_amount = int(booking.room.price)
    
    # Tạo link QR động từ VietQR
    qr_url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-compact2.png?amount={total_amount}&addInfo=THANHTOAN{booking.id}&accountName={ACCOUNT_NAME}"
    
    return render(request, 'core/payment.html', {
        'booking': booking, 
        'qr_url': qr_url,
        'total_amount': total_amount
    })

# --- 2. QUẢN TRỊ VIÊN (Dashboard Việt Hóa 100%) ---
@user_passes_test(is_admin)
def admin_dashboard(request):
    """Trung tâm điều khiển với biểu đồ Tiếng Việt"""
    # Thống kê tổng quan
    total_revenue = Booking.objects.filter(Q(status='approved') | Q(status='completed')).aggregate(total=Sum('room__price'))['total'] or 0
    pending_bookings = Booking.objects.filter(status='pending').select_related('user', 'room')

    # DỮ LIỆU BIỂU ĐỒ 1: Trạng thái đơn hàng (Chuyển sang Tiếng Việt)
    status_translation = {
        'pending': 'Chờ duyệt',
        'approved': 'Đã chấp nhận',
        'rejected': 'Đã từ chối',
        'completed': 'Hoàn thành'
    }
    status_stats = Booking.objects.values('status').annotate(count=Count('id'))
    booking_labels = [status_translation.get(s['status'], s['status']) for s in status_stats]
    booking_data = [s['count'] for s in status_stats]

    # DỮ LIỆU BIỂU ĐỒ 2: Phân bổ phòng theo Khu vực
    room_stats = Room.objects.values('address').annotate(count=Count('id'))
    room_labels = [r['address'] for r in room_stats]
    room_data = [r['count'] for r in room_stats]

    context = {
        'total_revenue': total_revenue,
        'pending_bookings': pending_bookings,
        'pending_count': pending_bookings.count(),
        'room_count': Room.objects.count(),
        'user_count': User.objects.count(),
        # Truyền dữ liệu sang JavaScript cho Chart.js
        'booking_labels': booking_labels,
        'booking_data': booking_data,
        'room_labels': room_labels,
        'room_data': room_data,
    }
    return render(request, 'core/dashboard.html', context)

# --- 3. CHI TIẾT PHÒNG & XỬ LÝ ĐẶT PHÒNG ---
def room_detail(request, pk):
    """Xem chi tiết, đặt phòng và gửi đánh giá"""
    room = get_object_or_404(Room, pk=pk)
    reviews = room.reviews.select_related('user').order_by('-created_at')
    services = Service.objects.all()

    if request.method == 'POST':
        # Xử lý khi khách bấm "Đặt phòng"
        if 'book_room' in request.POST:
            if not request.user.is_authenticated:
                messages.warning(request, "Bạn cần đăng nhập để đặt phòng.")
                return redirect('login')
            
            try:
                check_in = datetime.strptime(request.POST.get('check_in'), '%Y-%m-%d').date()
                check_out = datetime.strptime(request.POST.get('check_out'), '%Y-%m-%d').date()

                if check_out <= check_in:
                    messages.error(request, "Ngày trả phòng phải sau ngày nhận phòng.")
                else:
                    booking = Booking.objects.create(
                        user=request.user, room=room, 
                        check_in=check_in, check_out=check_out, status='pending'
                    )
                    booking.services.set(request.POST.getlist('services'))
                    messages.success(request, "Yêu cầu đặt phòng đã được gửi!")
                    return redirect('payment_page', booking_id=booking.id)
            except Exception:
                messages.error(request, "Vui lòng nhập ngày tháng hợp lệ.")

        # Xử lý khi khách gửi "Đánh giá"
        elif 'submit_review' in request.POST:
            if not request.user.is_authenticated:
                messages.error(request, "Đăng nhập để gửi nhận xét.")
            else:
                Review.objects.create(
                    room=room, user=request.user,
                    rating=int(request.POST.get('rating', 5)),
                    comment=request.POST.get('comment', '')
                )
                messages.success(request, "Cảm ơn bạn đã đánh giá!")
                return redirect('room_detail', pk=pk)

    return render(request, 'core/room_detail.html', {
        'room': room, 'reviews': reviews, 'services': services
    })

# --- 4. CÁC TÍNH NĂNG CƠ BẢN ---
def home(request):
    """Trang chủ hiển thị danh sách phòng và tìm kiếm"""
    query = request.GET.get('q', '').strip()
    destinations = Destination.objects.all()
    rooms = Room.objects.select_related('room_type').all().order_by('-is_available')
    
    if query:
        rooms = rooms.filter(Q(room_number__icontains=query) | Q(address__icontains=query)).distinct()
        
    return render(request, 'core/home.html', {
        'rooms': rooms, 'destinations': destinations, 'query': query
    })

@login_required
def my_bookings(request):
    """Xem lịch sử đặt phòng cá nhân"""
    bookings = Booking.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'core/my_bookings.html', {'bookings': bookings})

@user_passes_test(is_admin)
def manage_booking(request, pk, action):
    """Duyệt hoặc từ chối đơn hàng từ Admin Dashboard"""
    booking = get_object_or_404(Booking, pk=pk)
    if action == 'approve':
        booking.status, booking.room.is_available = 'approved', False
    elif action == 'reject':
        booking.status, booking.room.is_available = 'rejected', True
    booking.room.save()
    booking.save()
    return redirect('admin_dashboard')

# --- 5. HỆ THỐNG PHỤ TRỢ (AI & SETUP) ---
def ai_assistant(request):
    """Trợ lý AI tư vấn phòng bằng Groq Cloud"""
    user_msg = request.GET.get('message', '').strip()
    api_key = os.environ.get('GROQ_API_KEY')
    
    if not user_msg or not api_key:
        return JsonResponse({'reply': "Tôi có thể giúp gì cho bạn?"})
    
    try:
        client = Groq(api_key=api_key.strip())
        rooms = Room.objects.filter(is_available=True)[:2]
        context = ", ".join([f"Phòng {r.room_number} giá {int(r.price):,}đ" for r in rooms])
        
        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": f"Lễ tân MyHotel, trả lời tiếng Việt: {user_msg}. Dữ liệu: {context}"}],
            model="llama3-8b-8192",
        )
        return JsonResponse({'reply': chat.choices[0].message.content})
    except:
        return JsonResponse({'reply': "AI đang bận, thử lại sau nhé!"})

def setup_database(request):
    """Lệnh khởi tạo nhanh cho Render"""
    try:
        call_command('migrate')
        if not User.objects.filter(username='admin_moi').exists():
            User.objects.create_superuser('admin_moi', 'admin@hotel.com', 'admin12345')
        return HttpResponse("Hệ thống đã sẵn sàng!")
    except Exception as e:
        return HttpResponse(f"Lỗi: {e}")