import os
import google.generativeai as genai
from datetime import datetime
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.http import JsonResponse, HttpResponse
from django.core.management import call_command

# Import đầy đủ các Model của dự án
from .models import Room, Booking, Destination, Review, Service

# --- KIỂM TRA QUYỀN TRUY CẬP ---
def is_admin(user):
    """Xác định người dùng có quyền vào trang quản trị hay không"""
    return user.is_authenticated and user.is_staff

# --- 1. TRANG CHỦ, TÌM KIẾM & ĐIỂM ĐẾN ---
def home(request):
    """
    Xử lý hiển thị trang chủ.
    - Lấy danh sách điểm đến.
    - Tìm kiếm phòng theo số phòng, địa chỉ hoặc tên loại phòng.
    - Sắp xếp phòng trống lên đầu để khách dễ đặt.
    """
    query = request.GET.get('q', '').strip()
    destinations = Destination.objects.all()
    
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
    """
    Tạo mã QR VietQR động.
    - BANK_ID: Ngân hàng quân đội MB.
    - Ép kiểu int cho số tiền để tránh lỗi hiển thị trên môi trường Render.
    """
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    BANK_ID = "MB" 
    ACCOUNT_NO = "0987654321" 
    ACCOUNT_NAME = "KHACH SAN MYHOTEL"
    
    try:
        amount = int(booking.room.price) if booking.room.price else 0
    except (ValueError, TypeError):
        amount = 0
        
    description = f"MYHOTEL{booking.id}"
    qr_url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-compact2.png?amount={amount}&addInfo={description}&accountName={ACCOUNT_NAME}"
    
    return render(request, 'core/payment.html', {
        'booking': booking, 
        'qr_url': qr_url,
        'description': description,
        'total_price': amount
    })

# --- 3. QUẢN TRỊ VIÊN - DASHBOARD & THỐNG KÊ CHI TIẾT ---
@user_passes_test(is_admin)
def admin_dashboard(request):
    """
    Trung tâm điều hành của Admin.
    - Thống kê doanh thu thực tế từ các đơn đã duyệt.
    - Chuẩn bị dữ liệu mảng cho Chart.js hiển thị biểu đồ.
    - Liệt kê các đơn hàng 'pending' cần xử lý ngay.
    """
    total_revenue = Booking.objects.filter(
        status__in=['approved', 'completed']
    ).aggregate(total=Sum('room__price'))['total'] or 0
    
    pending_bookings = Booking.objects.filter(status='pending').select_related('user', 'room').order_by('-id')

    # Mapping trạng thái sang tiếng Việt cho biểu đồ
    status_map = {'pending': 'Chờ duyệt', 'approved': 'Đã duyệt', 'rejected': 'Từ chối', 'completed': 'Hoàn thành'}
    status_stats = Booking.objects.values('status').annotate(total=Count('id'))
    
    booking_labels = [status_map.get(s['status'], s['status']) for s in status_stats]
    booking_data = [s['total'] for s in status_stats]

    # Thống kê phòng theo khu vực
    room_stats = Room.objects.values('address').annotate(total=Count('id'))
    
    context = {
        'total_revenue': total_revenue,
        'pending_bookings': pending_bookings,
        'booking_labels': booking_labels,
        'booking_data': booking_data,
        'room_labels': [r['address'] for r in room_stats],
        'room_data': [r['total'] for r in room_stats],
        'room_count': Room.objects.count(),
        'user_count': User.objects.count(),
        'booking_total': Booking.objects.count(),
    }
    return render(request, 'core/dashboard.html', context)

# --- 4. CHI TIẾT PHÒNG, ĐẶT PHÒNG & ĐÁNH GIÁ TỪ KHÁCH ---
def room_detail(request, pk):
    """
    Xử lý logic tại trang chi tiết phòng.
    - Hiển thị thông tin phòng, dịch vụ đi kèm và các đánh giá cũ.
    - Xử lý Form đặt phòng (kiểm tra ngày nhận/trả).
    - Xử lý Form gửi đánh giá (rating & comment).
    """
    room = get_object_or_404(Room, pk=pk)
    reviews = room.reviews.select_related('user').order_by('-created_at')
    services = Service.objects.all()
    
    if request.method == 'POST':
        # 4.1 Xử lý đặt phòng
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
                    messages.error(request, "Lỗi: Ngày trả phòng không thể trước hoặc trùng ngày nhận.")
                else:
                    booking = Booking.objects.create(
                        user=request.user, room=room, 
                        check_in=check_in, check_out=check_out, status='pending'
                    )
                    messages.success(request, "Đã tạo đơn đặt phòng thành công!")
                    return redirect('payment_page', booking_id=booking.id)
            except (ValueError, TypeError):
                messages.error(request, "Định dạng ngày tháng bạn nhập không hợp lệ.")

        # 4.2 Xử lý gửi đánh giá
        elif 'submit_review' in request.POST:
            if request.user.is_authenticated:
                rating = request.POST.get('rating', 5)
                comment = request.POST.get('comment', '').strip()
                if comment:
                    Review.objects.create(
                        room=room, user=request.user,
                        rating=int(rating), comment=comment
                    )
                    messages.success(request, "Cảm ơn bạn đã để lại ý kiến đóng góp!")
                return redirect('room_detail', pk=pk)

    return render(request, 'core/room_detail.html', {
        'room': room, 
        'reviews': reviews, 
        'services': services
    })

# --- 5. ĐIỀU PHỐI ĐƠN HÀNG (QUYỀN ADMIN) ---
@user_passes_test(is_admin)
def manage_booking(request, pk, action):
    """
    Cho phép Admin duyệt đơn từ Dashboard.
    - 'approve': Đổi trạng thái đơn và khóa phòng (is_available = False).
    - 'reject': Đổi trạng thái đơn và mở lại phòng.
    """
    booking = get_object_or_404(Booking, pk=pk)
    
    if action == 'approve':
        booking.status = 'approved'
        booking.room.is_available = False
        messages.success(request, f"Đã phê duyệt đơn #{booking.id}")
    elif action == 'reject':
        booking.status = 'rejected'
        booking.room.is_available = True
        messages.warning(request, f"Đã từ chối đơn #{booking.id}")
    
    booking.room.save()
    booking.save()
    return redirect('admin_dashboard')

# --- 6. TRỢ LÝ ẢO AI (NÂNG CẤP VỚI GOOGLE GEMINI) ---
def ai_assistant(request):
    """
    Chatbot Gemini thế hệ mới.
    - Sử dụng model gemini-1.5-flash cực nhanh.
    - Tự động lấy tên người dùng để chào hỏi thân thiện.
    - Cung cấp dữ liệu thực tế từ Database để AI trả lời chính xác thông tin phòng.
    """
    user_msg = request.GET.get('message', '').strip()
    api_key = os.environ.get('GEMINI_API_KEY')
    
    if not user_msg:
        return JsonResponse({'reply': "Chào bạn! Tôi là trợ lý ảo của MyHotel. Tôi có thể giúp gì cho bạn?"})
    
    if not api_key:
        return JsonResponse({'reply': "Hệ thống AI hiện đang bảo trì API Key."})
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Tạo ngữ cảnh thông minh: AI biết được phòng nào đang trống
        active_rooms = Room.objects.filter(is_available=True)[:3]
        room_data = ", ".join([f"Phòng {r.room_number} ({r.price}đ)" for r in active_rooms])
        
        user_name = request.user.username if request.user.is_authenticated else "khách hàng"
        
        prompt = f"""
        Bạn là nhân viên lễ tân của khách sạn MyHotel. Hãy trả lời {user_name} thật lịch sự.
        Dữ liệu phòng trống hiện tại: {room_data}.
        Câu hỏi của khách: {user_msg}
        Hãy tư vấn dựa trên dữ liệu trên và trả lời bằng tiếng Việt ngắn gọn.
        """
        
        response = model.generate_content(prompt)
        return JsonResponse({'reply': response.text})
    except Exception as e:
        return JsonResponse({'reply': f"AI đang gặp lỗi kỹ thuật: {str(e)}"})

# --- 7. QUẢN LÝ TÀI KHOẢN & HỆ THỐNG RENDER ---
def register(request):
    """Xử lý đăng ký tài khoản mới cho khách hàng."""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            user = form.save()
            messages.success(request, f'Chúc mừng {user.username}! Bạn đã có thể đăng nhập.')
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

@login_required
def my_bookings(request):
    """Trang 'Chỗ nghỉ của tôi' hiển thị lịch sử đặt phòng của cá nhân."""
    # Dùng select_related('room') để tránh lỗi 500 khi truy cập dữ liệu liên kết trên Render.
    bookings = Booking.objects.filter(user=request.user).select_related('room').order_by('-id')
    return render(request, 'core/my_bookings.html', {'bookings': bookings})

@login_required
def cancel_booking(request, pk):
    """Cho phép khách hàng tự hủy đơn hàng nếu chưa được Admin duyệt."""
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    if booking.status == 'pending':
        booking.delete()
        messages.success(request, "Đã hủy đơn hàng thành công.")
    else:
        messages.error(request, "Đơn hàng này đã được xử lý, bạn không thể tự hủy.")
    return redirect('my_bookings')

def setup_database(request):
    """
    Công cụ khởi tạo hệ thống dành riêng cho Render.
    - Tự động chạy migrate.
    - Tự động tạo tài khoản Superuser để Đức có quyền Admin ngay lập tức.
    """
    try:
        call_command('migrate')
        if not User.objects.filter(username='admin_moi').exists():
            User.objects.create_superuser('admin_moi', 'admin@hotel.com', 'admin12345')
            return HttpResponse("Khởi tạo thành công! User: admin_moi | Pass: admin12345")
        return HttpResponse("Hệ thống đã được thiết lập từ trước đó.")
    except Exception as e:
        return HttpResponse(f"Lỗi khởi tạo: {str(e)}")