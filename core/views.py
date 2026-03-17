import os
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.http import JsonResponse, HttpResponse
from django.core.management import call_command

# Import Groq an toàn để không gây lỗi 500 nếu chưa cài thư viện
try:
    from groq import Groq
except ImportError:
    Groq = None

from .models import Room, Booking, Destination, Review, Service

# --- KIỂM TRA QUYỀN ADMIN ---
def is_admin(user):
    """Xác định người dùng có quyền quản trị không"""
    return user.is_authenticated and user.is_staff

# --- 1. TRANG CHỦ & TÌM KIẾM ---
def home(request):
    """Hiển thị danh sách phòng và lọc theo từ khóa"""
    query = request.GET.get('q', '').strip()
    destinations = Destination.objects.all()
    rooms = Room.objects.all().order_by('-is_available', 'price')
    
    if query:
        rooms = rooms.filter(
            Q(room_number__icontains=query) | 
            Q(address__icontains=query)
        ).distinct()
        
    return render(request, 'core/home.html', {
        'rooms': rooms, 
        'destinations': destinations, 
        'query': query
    })

# --- 2. THANH TOÁN QR (SỬA LỖI 500) ---
@login_required
def payment_page(request, booking_id):
    """Hiển thị mã QR VietQR để khách hàng thanh toán"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    # Thông tin tài khoản nhận (Thay đổi theo ý bạn)
    BANK_ID = "MB" 
    ACCOUNT_NO = "0987654321" 
    ACCOUNT_NAME = "KHACH SAN MYHOTEL"
    
    # Đảm bảo số tiền là số nguyên để tránh lỗi URL QR
    amount = int(booking.room.price)
    
    # Tạo link QR động theo tiêu chuẩn VietQR
    qr_url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-compact2.png?amount={amount}&addInfo=MYHOTEL{booking.id}&accountName={ACCOUNT_NAME}"
    
    return render(request, 'core/payment.html', {
        'booking': booking, 
        'qr_url': qr_url
    })

# --- 3. QUẢN TRỊ (DASHBOARD TIẾNG VIỆT) ---
@user_passes_test(is_admin)
def admin_dashboard(request):
    """Thống kê doanh thu và dữ liệu biểu đồ nhãn Tiếng Việt"""
    # Tính tổng doanh thu từ các đơn đã duyệt hoặc hoàn thành
    total_revenue = Booking.objects.filter(
        status__in=['approved', 'completed']
    ).aggregate(total=Sum('room__price'))['total'] or 0
    
    pending_bookings = Booking.objects.filter(status='pending').select_related('user', 'room')

    # Việt hóa nhãn biểu đồ Trạng thái (Dùng cho Chart.js)
    status_map = {
        'pending': 'Chờ duyệt', 
        'approved': 'Đã duyệt', 
        'rejected': 'Từ chối', 
        'completed': 'Xong'
    }
    status_stats = Booking.objects.values('status').annotate(total=Count('id'))
    booking_labels = [status_map.get(s['status'], s['status']) for s in status_stats]
    booking_data = [s['total'] for s in status_stats]

    # Dữ liệu biểu đồ Khu vực
    room_stats = Room.objects.values('address').annotate(total=Count('id'))
    room_labels = [r['address'] for r in room_stats]
    room_data = [r['total'] for r in room_stats]

    context = {
        'total_revenue': total_revenue,
        'pending_bookings': pending_bookings,
        'booking_labels': booking_labels,
        'booking_data': booking_data,
        'room_labels': room_labels,
        'room_data': room_data,
        'room_count': Room.objects.count(),
        'user_count': User.objects.count(),
    }
    return render(request, 'core/dashboard.html', context)

# --- 4. CHI TIẾT PHÒNG & ĐẶT PHÒNG ---
def room_detail(request, pk):
    """Xem chi tiết phòng và xử lý đặt phòng/đánh giá"""
    room = get_object_or_404(Room, pk=pk)
    reviews = room.reviews.select_related('user').order_by('-created_at')
    
    if request.method == 'POST':
        # Xử lý Đặt phòng
        if 'book_room' in request.POST:
            if not request.user.is_authenticated:
                return redirect('login')
            try:
                check_in = datetime.strptime(request.POST.get('check_in'), '%Y-%m-%d').date()
                check_out = datetime.strptime(request.POST.get('check_out'), '%Y-%m-%d').date()
                
                if check_out <= check_in:
                    messages.error(request, "Ngày trả phòng phải sau ngày nhận.")
                else:
                    booking = Booking.objects.create(
                        user=request.user, room=room, 
                        check_in=check_in, check_out=check_out, status='pending'
                    )
                    return redirect('payment_page', booking_id=booking.id)
            except:
                messages.error(request, "Lỗi định dạng ngày tháng.")

        # Xử lý Gửi đánh giá
        elif 'submit_review' in request.POST:
            if request.user.is_authenticated:
                Review.objects.create(
                    room=room, user=request.user,
                    rating=int(request.POST.get('rating', 5)),
                    comment=request.POST.get('comment', '')
                )
                messages.success(request, "Cảm ơn bạn đã đánh giá!")
                return redirect('room_detail', pk=pk)

    return render(request, 'core/room_detail.html', {
        'room': room, 
        'reviews': reviews, 
        'services': Service.objects.all()
    })

# --- 5. QUẢN LÝ ĐƠN HÀNG (DÀNH CHO ADMIN) ---
@user_passes_test(is_admin)
def manage_booking(request, pk, action):
    """Duyệt hoặc từ chối đơn hàng nhanh từ Dashboard"""
    booking = get_object_or_404(Booking, pk=pk)
    if action == 'approve':
        booking.status, booking.room.is_available = 'approved', False
    elif action == 'reject':
        booking.status, booking.room.is_available = 'rejected', True
    booking.room.save()
    booking.save()
    messages.success(request, f"Đã cập nhật đơn hàng #{booking.id}")
    return redirect('admin_dashboard')

# --- 6. TRỢ LÝ AI ---
def ai_assistant(request):
    """Chatbot tư vấn sử dụng Groq API"""
    user_msg = request.GET.get('message', '').strip()
    api_key = os.environ.get('GROQ_API_KEY')
    
    if not user_msg or not api_key or not Groq:
        return JsonResponse({'reply': "Chào bạn, MyHotel có thể giúp gì cho bạn?"})
    
    try:
        client = Groq(api_key=api_key)
        chat = client.chat.completions.create(
            messages=[{"role": "user", "content": f"Bạn là lễ tân khách sạn, trả lời tiếng Việt: {user_msg}"}],
            model="llama3-8b-8192",
        )
        return JsonResponse({'reply': chat.choices[0].message.content})
    except:
        return JsonResponse({'reply': "AI hiện đang bảo trì, vui lòng quay lại sau."})

# --- 7. HỆ THỐNG & KHÁCH HÀNG ---
@login_required
def my_bookings(request):
    """Xem danh sách đơn hàng của khách hàng hiện tại"""
    bookings = Booking.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'core/my_bookings.html', {'bookings': bookings})

def setup_database(request):
    """Lệnh khởi tạo nhanh khi Deploy lên Render"""
    try:
        call_command('migrate')
        if not User.objects.filter(username='admin_moi').exists():
            User.objects.create_superuser('admin_moi', 'admin@hotel.com', 'admin12345')
        return HttpResponse("Khởi tạo Database thành công!")
    except Exception as e:
        return HttpResponse(f"Lỗi setup: {e}")