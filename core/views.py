from django.shortcuts import redirect, render, get_object_or_404
from django.http import HttpResponse
from django.db import models
from .models import Room, Booking, Destination, Review
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.utils import timezone
from datetime import datetime
from django.contrib.auth.models import User
from django.core.management import call_command
# Trong hàm home của bạn:
call_command('loaddata', 'du_lieu_phong.json')

# 1. Trang chủ: Xử lý hiển thị địa điểm, tìm kiếm và bộ lọc
def home(request):
    # TỰ ĐỘNG TẠO ADMIN (Để cứu cánh khi không có quyền Shell trên Render)
    # Sau khi đăng nhập thành công, bạn nên xóa đoạn này để bảo mật.
    if not User.objects.filter(username='admin_moi').exists():
        User.objects.create_superuser('admin_moi', 'admin@example.com', 'Matkhau123@')

    query = request.GET.get('q')
    if query:
        # Tìm kiếm theo địa chỉ, số phòng, loại phòng hoặc mô tả
        rooms = Room.objects.filter(
            models.Q(address__icontains=query) | 
            models.Q(room_number__icontains=query) | 
            models.Q(room_type__name__icontains=query) |
            models.Q(description__icontains=query),
            is_available=True
        ).distinct()
    else:
        rooms = Room.objects.filter(is_available=True)

    # Lấy danh sách địa điểm để hiển thị ở mục Điểm đến phổ biến
    destinations = Destination.objects.all()

    return render(request, 'core/home.html', {
        'rooms': rooms,
        'destinations': destinations
    })

# 2. Chi tiết phòng & Xử lý Đặt phòng + Đánh giá
def room_detail(request, pk):
    room = get_object_or_404(Room, pk=pk)
    # Lấy danh sách đánh giá của phòng này, mới nhất hiện lên đầu
    reviews = room.reviews.all().order_by('-created_at') 
    
    if request.method == 'POST':
        # TRƯỜNG HỢP 1: Xử lý Đặt phòng
        if 'book_room' in request.POST:
            if not request.user.is_authenticated:
                messages.error(request, "Vui lòng đăng nhập để thực hiện đặt phòng.")
                return redirect('login') 

            check_in_str = request.POST.get('check_in')
            check_out_str = request.POST.get('check_out')

            if not check_in_str or not check_out_str:
                messages.error(request, "Vui lòng chọn đầy đủ ngày nhận và ngày trả phòng.")
            else:
                try:
                    check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
                    check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()

                    if check_out <= check_in:
                        messages.error(request, "Ngày trả phòng phải sau ngày nhận phòng.")
                    elif check_in < timezone.now().date():
                        messages.error(request, "Không thể đặt phòng cho ngày trong quá khứ.")
                    else:
                        Booking.objects.create(
                            user=request.user,
                            room=room,
                            check_in=check_in,
                            check_out=check_out,
                            status='pending' 
                        )
                        messages.success(request, f"Đơn đặt phòng {room.room_number} đã được gửi thành công!")
                        return redirect('my_bookings')
                except ValueError:
                    messages.error(request, "Định dạng ngày tháng không hợp lệ.")

        # TRƯỜNG HỢP 2: Xử lý Gửi đánh giá
        elif 'submit_review' in request.POST:
            if not request.user.is_authenticated:
                messages.error(request, "Bạn cần đăng nhập để viết đánh giá.")
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
                messages.success(request, "Cảm ơn bạn đã để lại đánh giá!")
                return redirect('room_detail', pk=pk)

    return render(request, 'core/room_detail.html', {
        'room': room,
        'reviews': reviews
    })

# 3. Danh sách phòng đã đặt của tôi
@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'core/my_bookings.html', {'bookings': bookings})

# 4. Hủy đơn đặt phòng
@login_required
def cancel_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    if request.method == 'POST':
        if booking.status == 'pending':
            booking.delete()
            messages.success(request, "Đã hủy đơn đặt phòng thành công.")
        else:
            messages.error(request, "Không thể hủy đơn đã được quản trị viên xử lý.")
    return redirect('my_bookings')
from django.core.management import call_command
def load_my_data(request):
    try:
        call_command('loaddata', 'du_lieu_phong.json')
        return HttpResponse("Đã nạp dữ liệu thành công!")
    except Exception as e:
        return HttpResponse(f"Lỗi: {e}")