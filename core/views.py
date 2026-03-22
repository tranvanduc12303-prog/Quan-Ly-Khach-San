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

# Import các Model của dự án MyHotel
from .models import Room, Booking, Destination, Review, Service

# =================================================================
# 1. HỆ THỐNG KIỂM TRA QUYỀN (PERMISSIONS)
# =================================================================

def is_admin(user):
    """Kiểm tra xem người dùng có phải là Admin/Staff không"""
    return user.is_authenticated and user.is_staff

# =================================================================
# 2. QUẢN LÝ TRANG CHỦ & TÌM KIẾM PHÒNG
# =================================================================

def home(request):
    """
    Xử lý hiển thị danh sách phòng và điểm đến.
    Hỗ trợ tìm kiếm theo số phòng, địa chỉ hoặc loại phòng.
    """
    query = request.GET.get('q', '').strip()
    destinations = Destination.objects.all()
    
    # Ưu tiên hiển thị phòng trống lên trước
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

# =================================================================
# 3. CHI TIẾT PHÒNG, ĐẶT PHÒNG & ĐÁNH GIÁ
# =================================================================

def room_detail(request, pk):
    """
    Hiển thị chi tiết một phòng khách sạn.
    Xử lý 2 tác vụ POST: Đặt phòng và Gửi đánh giá.
    """
    room = get_object_or_404(Room, pk=pk)
    reviews = room.reviews.select_related('user').order_by('-created_at')
    services = Service.objects.all()
    
    if request.method == 'POST':
        # Tác vụ 1: Đặt phòng
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
                    messages.error(request, "Ngày trả phòng phải sau ngày nhận phòng.")
                else:
                    booking = Booking.objects.create(
                        user=request.user, 
                        room=room, 
                        check_in=check_in, 
                        check_out=check_out, 
                        status='pending'
                    )
                    messages.success(request, "Đã gửi yêu cầu đặt phòng!")
                    return redirect('payment_page', booking_id=booking.id)
            except (ValueError, TypeError):
                messages.error(request, "Vui lòng nhập đúng định dạng ngày.")

        # Tác vụ 2: Gửi đánh giá
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
                    messages.success(request, "Cảm ơn bạn đã đánh giá!")
                return redirect('room_detail', pk=pk)

    return render(request, 'core/room_detail.html', {
        'room': room, 
        'reviews': reviews, 
        'services': services
    })

# =================================================================
# 4. TRANG CÁ NHÂN & QUẢN LÝ LỊCH SỬ ĐẶT PHÒNG
# =================================================================

@login_required
def profile(request):
    """
    Trang thông tin cá nhân của người dùng.
    Hiển thị thông tin cơ bản và các đơn đặt phòng gần đây.
    """
    user = request.user
    user_bookings = Booking.objects.filter(user=user).select_related('room').order_by('-id')
    
    # Tính toán một số thống kê nhanh cho profile
    stats = {
        'total': user_bookings.count(),
        'approved': user_bookings.filter(status='approved').count(),
        'pending': user_bookings.filter(status='pending').count(),
    }
    
    context = {
        'user': user,
        'bookings': user_bookings,
        'stats': stats
    }
    return render(request, 'core/profile.html', context)

@login_required
def edit_profile(request):
    """Cập nhật thông tin cá nhân của người dùng."""
    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.email = request.POST.get('email', '')
        request.user.save()
        messages.success(request, "Đã cập nhật hồ sơ thành công!")
        return redirect('profile')
    return render(request, 'core/edit_profile.html')

@login_required
def my_bookings(request):
    """Hiển thị danh sách tất cả phòng khách đã đặt."""
    bookings = Booking.objects.filter(user=request.user).select_related('room').order_by('-id')
    return render(request, 'core/my_bookings.html', {'bookings': bookings})

@login_required
def cancel_booking(request, pk):
    """Cho phép khách hàng tự hủy đơn khi đang ở trạng thái Chờ duyệt."""
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    if booking.status == 'pending':
        booking.delete()
        messages.success(request, "Đã hủy đơn hàng.")
    else:
        messages.error(request, "Không thể hủy đơn đã qua xử lý.")
    return redirect('my_bookings')

# =================================================================
# 5. HỆ THỐNG THANH TOÁN VIETQR
# =================================================================

@login_required
def payment_page(request, booking_id):
    """Tạo mã QR thanh toán động cho từng đơn hàng."""
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    # Cấu hình thông tin thụ hưởng
    bank_id = "MB" 
    account_no = "0987654321" 
    account_name = "KHACH SAN MYHOTEL"
    
    amount = int(booking.room.price) if booking.room.price else 0
    description = f"MYHOTEL{booking.id}"
    
    # URL gọi API VietQR để tạo ảnh QR
    qr_url = (
        f"https://img.vietqr.io/image/{bank_id}-{account_no}-compact2.png"
        f"?amount={amount}&addInfo={description}&accountName={account_name}"
    )
    
    return render(request, 'core/payment.html', {
        'booking': booking, 
        'qr_url': qr_url,
        'total_price': amount
    })

# =================================================================
# 6. DASHBOARD QUẢN TRỊ (ADMIN ONLY)
# =================================================================

@user_passes_test(is_admin)
def admin_dashboard(request):
    """Trang thống kê tổng quan dành cho quản lý khách sạn."""
    # Thống kê doanh thu từ các đơn đã thanh toán/duyệt
    revenue_data = Booking.objects.filter(
        status__in=['approved', 'completed']
    ).aggregate(total=Sum('room__price'))
    total_revenue = revenue_data['total'] or 0
    
    # Danh sách chờ xử lý
    pending_list = Booking.objects.filter(status='pending').select_related('user', 'room').order_by('-id')

    # Dữ liệu cho biểu đồ Chart.js
    status_counts = Booking.objects.values('status').annotate(total=Count('id'))
    status_map = {'pending': 'Chờ', 'approved': 'Duyệt', 'rejected': 'Hủy', 'completed': 'Xong'}
    
    labels = [status_map.get(s['status'], s['status']) for s in status_counts]
    values = [s['total'] for s in status_counts]

    context = {
        'total_revenue': total_revenue,
        'pending_bookings': pending_list,
        'booking_labels': labels,
        'booking_data': values,
        'room_count': Room.objects.count(),
        'user_count': User.objects.count(),
    }
    return render(request, 'core/dashboard.html', context)

@user_passes_test(is_admin)
def manage_booking(request, pk, action):
    """Admin phê duyệt hoặc từ chối đơn đặt phòng."""
    booking = get_object_or_404(Booking, pk=pk)
    
    if action == 'approve':
        booking.status = 'approved'
        booking.room.is_available = False # Khóa phòng khi đã duyệt
    elif action == 'reject':
        booking.status = 'rejected'
        booking.room.is_available = True
    
    booking.room.save()
    booking.save()
    messages.info(request, f"Đã cập nhật trạng thái đơn #{booking.id}")
    return redirect('admin_dashboard')

# =================================================================
# 7. TRỢ LÝ AI & TIỆN ÍCH HỆ THỐNG
# =================================================================

def ai_assistant(request):
    """Tích hợp Google Gemini AI để tư vấn phòng cho khách."""
    user_query = request.GET.get('message', '').strip()
    api_key = os.environ.get('GEMINI_API_KEY')
    
    if not user_query:
        return JsonResponse({'reply': "Chào bạn! Tôi có thể giúp gì cho bạn hôm nay?"})
    
    if not api_key:
        return JsonResponse({'reply': "AI đang bận, vui lòng thử lại sau."})
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Cung cấp dữ liệu thực tế cho AI
        rooms_available = Room.objects.filter(is_available=True)[:3]
        info = ", ".join([f"Phòng {r.room_number} giá {r.price}" for r in rooms_available])
        
        prompt = f"Bạn là lễ tân khách sạn. Hãy tư vấn ngắn gọn. Dữ liệu phòng trống: {info}. Câu hỏi: {user_query}"
        response = model.generate_content(prompt)
        
        return JsonResponse({'reply': response.text})
    except Exception as e:
        return JsonResponse({'reply': f"Lỗi hệ thống AI: {str(e)}"})

def register(request):
    """Đăng ký tài khoản người dùng mới."""
    if request.method == 'POST':
        form = UserCreationForm(request.POST)
        if form.is_valid():
            form.save()
            messages.success(request, "Đăng ký thành công! Hãy đăng nhập.")
            return redirect('login')
    else:
        form = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form})

def setup_database(request):
    """Lệnh khởi tạo nhanh dành cho Render (Chạy Migration và tạo Admin)."""
    try:
        call_command('migrate')
        if not User.objects.filter(username='admin_moi').exists():
            User.objects.create_superuser('admin_moi', 'admin@hotel.com', 'admin12345')
            return HttpResponse("Khởi tạo thành công tài khoản admin_moi!")
        return HttpResponse("Hệ thống đã ổn định.")
    except Exception as e:
        return HttpResponse(f"Lỗi: {str(e)}")

# Kết thúc file views.py