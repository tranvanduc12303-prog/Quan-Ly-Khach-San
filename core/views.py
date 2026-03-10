from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.db.models import Q
from django.utils import timezone
from datetime import datetime
from .models import Room, Booking, Destination, Review

# 1. TRANG CHỦ: Tìm kiếm và hiển thị phòng
def home(request):
    # Tự động tạo tài khoản admin nếu chưa có (User: admin_moi / Pass: Matkhau123@)
    if not User.objects.filter(username='admin_moi').exists():
        User.objects.create_superuser('admin_moi', 'admin@example.com', 'Matkhau123@')

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

# 2. CHI TIẾT PHÒNG: Đặt phòng và Đánh giá
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
                messages.warning(request, "Đăng nhập để để lại đánh giá.")
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

    return render(request, 'core/room_detail.html', {
        'room': room,
        'reviews': reviews
    })

# 3. QUẢN LÝ ĐẶT PHÒNG CỦA TÔI
@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(user=request.user).order_by('-created_at')
    return render(request, 'core/my_bookings.html', {'bookings': bookings})

# 4. HỦY ĐẶT PHÒNG
@login_required
def cancel_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    if booking.status == 'pending':
        booking.delete()
        messages.success(request, "Đã hủy đơn đặt phòng.")
    else:
        messages.error(request, "Không thể hủy đơn đã duyệt.")
    return redirect('my_bookings')
from django.http import HttpResponse
from django.core.management import call_command
from django.contrib.auth.models import User

def setup_database(request):
    # Chạy migrate
    call_command('migrate')
    # Tạo admin nếu chưa có
    if not User.objects.filter(username='admin_moi').exists():
        User.objects.create_superuser('admin_moi', 'admin@example.com', 'matkhau123')
        return HttpResponse("Đã migrate và tạo tài khoản admin_moi thành công!")
    return HttpResponse("Hệ thống đã sẵn sàng.")