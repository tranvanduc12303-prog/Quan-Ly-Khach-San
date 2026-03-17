import os
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.http import JsonResponse, HttpResponse
from django.core.management import call_command

# --- CẤU HÌNH AI & THƯ VIỆN ---
try:
    from groq import Groq
except ImportError:
    Groq = None

from .models import Room, Booking, Destination, Review, Service

# --- KIỂM TRA QUYỀN TRUY CẬP ---
def is_admin(user):
    """Kiểm tra người dùng có phải là nhân viên/quản trị viên không"""
    return user.is_authenticated and user.is_staff

# --- 1. TRANG CHỦ, TÌM KIẾM & ĐIỂM ĐẾN ---
def home(request):
    """Hiển thị danh sách phòng, lọc theo từ khóa và hiển thị điểm đến"""
    query = request.GET.get('q', '').strip()
    destinations = Destination.objects.all()
    
    # Ưu tiên phòng còn trống lên trước
    rooms = Room.objects.all().order_by('-is_available', 'price')
    
    if query:
        rooms = rooms.filter(
            Q(room_number__icontains=query) | 
            Q(address__icontains=query) |
            Q(room_type__name__icontains=query)
        ).distinct()
        
    context = {
        'rooms': rooms, 
        'destinations': destinations, 
        'query': query,
        'room_count': rooms.count()
    }
    return render(request, 'core/home.html', context)

# --- 2. HỆ THỐNG THANH TOÁN QR (VIETQR) ---
@login_required
def payment_page(request, booking_id):
    """Xử lý hiển thị mã QR thanh toán động cho từng đơn hàng"""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    # Cấu hình tài khoản ngân hàng nhận tiền
    BANK_ID = "MB" 
    ACCOUNT_NO = "0987654321" 
    ACCOUNT_NAME = "KHACH SAN MYHOTEL"
    
    # Đảm bảo số tiền là số nguyên và tạo nội dung chuyển khoản duy nhất
    try:
        amount = int(booking.room.price)
    except (ValueError, TypeError):
        amount = 0
        
    description = f"MYHOTEL{booking.id}"
    
    # Tạo link VietQR theo tiêu chuẩn Napas
    qr_url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-compact2.png?amount={amount}&addInfo={description}&accountName={ACCOUNT_NAME}"
    
    return render(request, 'core/payment.html', {
        'booking': booking, 
        'qr_url': qr_url,
        'description': description,
        'total_price': amount
    })

# --- 3. QUẢN TRỊ VIÊN - DASHBOARD & THỐNG KÊ ---
@user_passes_test(is_admin)
def admin_dashboard(request):
    """Trang thống kê dành cho quản lý với dữ liệu biểu đồ tiếng Việt"""
    # 1. Thống kê doanh thu (Chỉ tính các đơn đã duyệt hoặc hoàn thành)
    total_revenue = Booking.objects.filter(
        status__in=['approved', 'completed']
    ).aggregate(total=Sum('room__price'))['total'] or 0
    
    # 2. Danh sách đơn hàng mới nhất cần xử lý
    pending_bookings = Booking.objects.filter(status='pending').select_related('user', 'room').order_by('-id')

    # 3. Chuẩn bị dữ liệu cho biểu đồ Trạng thái (Chart.js)
    status_map = {
        'pending': 'Chờ duyệt', 
        'approved': 'Đã duyệt', 
        'rejected': 'Từ chối', 
        'completed': 'Hoàn thành'
    }
    status_stats = Booking.objects.values('status').annotate(total=Count('id'))
    booking_labels = [status_map.get(s['status'], s['status']) for s in status_stats]
    booking_data = [s['total'] for s in status_stats]

    # 4. Chuẩn bị dữ liệu cho biểu đồ Khu vực
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
        'booking_total': Booking.objects.count(),
    }
    return render(request, 'core/dashboard.html', context)

# --- 4. CHI TIẾT PHÒNG, ĐẶT PHÒNG & ĐÁNH GIÁ ---
def room_detail(request, pk):
    """Xem chi tiết phòng và xử lý các hành động của khách hàng"""
    room = get_object_or_404(Room, pk=pk)
    reviews = room.reviews.select_related('user').order_by('-created_at')
    services = Service.objects.all()
    
    if request.method == 'POST':
        # Hành động 1: Khách hàng đặt phòng
        if 'book_room' in request.POST:
            if not request.user.is_authenticated:
                messages.warning(request, "Vui lòng đăng nhập để đặt phòng.")
                return redirect('login')
            
            try:
                check_in_str = request.POST.get('check_in')
                check_out_str = request.POST.get('check_out')
                check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
                check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()
                
                if check_out <= check_in:
                    messages.error(request, "Ngày trả phòng phải sau ngày nhận phòng.")
                else:
                    booking = Booking.objects.create(
                        user=request.user, 
                        room=room, 
                        check_in=check_in, 
                        check_out=check_out, 
                        status='pending'
                    )
                    messages.success(request, "Đơn đặt phòng đã được tạo. Vui lòng thanh toán.")
                    return redirect('payment_page', booking_id=booking.id)
            except (ValueError, TypeError):
                messages.error(request, "Định dạng ngày tháng không hợp lệ.")

        # Hành động 2: Khách hàng gửi đánh giá
        elif 'submit_review' in request.POST:
            if request.user.is_authenticated:
                rating = request.POST.get('rating', 5)
                comment = request.POST.get('comment', '').strip()
                if comment:
                    Review.objects.create(
                        room=room, 
                        user=request.user,
                        rating=int(rating),
                        comment=comment
                    )
                    messages.success(request, "Cảm ơn bạn đã gửi đánh giá!")
                return redirect('room_detail', pk=pk)

    return render(request, 'core/room_detail.html', {
        'room': room, 
        'reviews': reviews, 
        'services': services
    })

# --- 5. ĐIỀU PHỐI ĐƠN HÀNG (DÀNH CHO ADMIN) ---
@user_passes_test(is_admin)
def manage_booking(request, pk, action):
    """Admin phê duyệt hoặc từ chối đơn hàng nhanh chóng"""
    booking = get_object_or_404(Booking, pk=pk)
    
    if action == 'approve':
        booking.status = 'approved'
        booking.room.is_available = False # Đánh dấu phòng đã có người
        messages.success(request, f"Đã phê duyệt đơn hàng #{booking.id}")
    elif action == 'reject':
        booking.status = 'rejected'
        booking.room.is_available = True
        messages.warning(request, f"Đã từ chối đơn hàng #{booking.id}")
    
    booking.room.save()
    booking.save()
    return redirect('admin_dashboard')

# --- 6. TRỢ LÝ ẢO AI (AI ASSISTANT) ---
def ai_assistant(request):
    """Chatbot thông minh hỗ trợ khách hàng qua Groq API"""
    user_msg = request.GET.get('message', '').strip()
    api_key = os.environ.get('GROQ_API_KEY')
    
    if not user_msg or not api_key or not Groq:
        return JsonResponse({'reply': "Xin chào! Tôi là trợ lý ảo MyHotel. Tôi có thể giúp gì cho bạn?"})
    
    try:
        client = Groq(api_key=api_key)
        chat_completion = client.chat.completions.create(
            messages=[
                {"role": "system", "content": "Bạn là lễ tân khách sạn MyHotel chuyên nghiệp, thân thiện. Trả lời ngắn gọn bằng tiếng Việt."},
                {"role": "user", "content": user_msg}
            ],
            model="llama3-8b-8192",
        )
        return JsonResponse({'reply': chat_completion.choices[0].message.content})
    except Exception:
        return JsonResponse({'reply': "Rất tiếc, AI đang bận xử lý. Bạn vui lòng thử lại sau nhé!"})

# --- 7. QUẢN LÝ TÀI KHOẢN & HỆ THỐNG ---
@login_required
def my_bookings(request):
    """Trang 'Chỗ nghỉ của tôi' dành cho khách hàng kiểm tra lịch sử"""
    # Lấy đơn hàng và thông tin phòng đi kèm để tối ưu tốc độ tải trang
    bookings = Booking.objects.filter(user=request.user).select_related('room').order_by('-id')
    return render(request, 'core/my_bookings.html', {'bookings': bookings})

@login_required
def cancel_booking(request, pk):
    """Cho phép khách hàng tự hủy đơn khi đơn vẫn đang chờ duyệt"""
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    
    if booking.status == 'pending':
        booking.delete()
        messages.success(request, "Đã hủy đơn đặt phòng thành công.")
    else:
        messages.error(request, "Đơn hàng đã được xử lý, bạn không thể tự hủy.")
        
    return redirect('my_bookings')

def setup_database(request):
    """Công cụ khởi tạo hệ thống nhanh (Migrate & Superuser) cho Render"""
    try:
        # Chạy migrate để cập nhật cấu trúc bảng
        call_command('migrate')
        
        # Tạo tài khoản quản trị mặc định nếu chưa có
        if not User.objects.filter(username='admin_moi').exists():
            User.objects.create_superuser('admin_moi', 'admin@hotel.com', 'admin12345')
            return HttpResponse("Khởi tạo hệ thống thành công! Admin: admin_moi / Pass: admin12345")
        
        return HttpResponse("Hệ thống đã được thiết lập từ trước.")
    except Exception as e:
        return HttpResponse(f"Quá trình thiết lập gặp lỗi: {str(e)}")