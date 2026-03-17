import os
from groq import Groq
from datetime import datetime

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Count, Sum
from django.utils import timezone
from django.http import JsonResponse, HttpResponse
from django.core.management import call_command

from .models import Room, Booking, Destination, Review, RoomType, Service

# --- HỖ TRỢ PHÂN QUYỀN ---
def is_admin(user):
    return user.is_authenticated and user.is_staff

# --- 1. HỆ THỐNG AI TƯ VẤN (SỬ DỤNG GROQ LLAMA 3) ---
def ai_assistant(request):
    user_message = request.GET.get('message', '').strip()
    if not user_message:
        return JsonResponse({'reply': "Chào bạn! MyHotel có thể giúp gì cho bạn?"})

    api_key = os.environ.get('GROQ_API_KEY')
    try:
        client = Groq(api_key=api_key.strip())
        available_rooms = Room.objects.filter(is_available=True).select_related('room_type')[:3]
        room_info = [f"Phòng {r.room_number} ({r.room_type.name}) giá {int(r.price):,} VNĐ" for r in available_rooms]
        context = "Thông tin phòng trống: " + ", ".join(room_info) if room_info else "Hiện tại hết phòng."

        prompt = f"Bạn là nhân viên khách sạn MyHotel. {context}. Trả lời bằng tiếng Việt, thân thiện, ngắn gọn. Khách hỏi: {user_message}"
        
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192",
            temperature=0.7,
        )
        return JsonResponse({'reply': completion.choices[0].message.content.strip()})
    except:
        return JsonResponse({'reply': "Chatbot đang bận, bạn gọi hotline nhé!"})

# --- 2. TRANG CHỦ & TÌM KIẾM ---
def home(request):
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

# --- 3. CHI TIẾT PHÒNG & LOGIC ĐẶT PHÒNG ---
def room_detail(request, pk):
    room = get_object_or_404(Room, pk=pk)
    reviews = room.reviews.select_related('user').order_by('-created_at')
    services = Service.objects.all()

    if request.method == 'POST' and 'book_room' in request.POST:
        if not request.user.is_authenticated:
            messages.warning(request, "Vui lòng đăng nhập để đặt phòng.")
            return redirect('login')
        
        try:
            check_in = datetime.strptime(request.POST.get('check_in'), '%Y-%m-%d').date()
            check_out = datetime.strptime(request.POST.get('check_out'), '%Y-%m-%d').date()

            if check_out <= check_in:
                messages.error(request, "Ngày trả phòng phải sau ngày nhận.")
            elif not room.is_available:
                messages.error(request, "Phòng này vừa được đặt.")
            else:
                booking = Booking.objects.create(
                    user=request.user, room=room, 
                    check_in=check_in, check_out=check_out, status='pending'
                )
                selected_services = request.POST.getlist('services')
                if selected_services:
                    booking.services.set(selected_services)
                    booking.save()

                messages.success(request, "Đã tạo đơn đặt phòng thành công!")
                # CHUYỂN HƯỚNG SANG TRANG THANH TOÁN
                return redirect('payment_page', booking_id=booking.id)
        except:
            messages.error(request, "Lỗi định dạng ngày tháng.")

    return render(request, 'core/room_detail.html', {'room': room, 'reviews': reviews, 'services': services})

# --- 4. THANH TOÁN (VIETQR) ---
@login_required
def payment_page(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    # Thông tin ngân hàng của bạn (Demo)
    BANK_ID = "MB"
    ACCOUNT_NO = "0987654321" # Thay bằng số của bạn
    ACCOUNT_NAME = "KHACH SAN MYHOTEL"
    
    amount = booking.total_price
    description = f"MYHOTEL{booking.id}"
    
    # Tạo mã QR VietQR tự động điền số tiền và nội dung
    qr_url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-compact2.png?amount={amount}&addInfo={description}&accountName={ACCOUNT_NAME}"
    
    return render(request, 'core/payment.html', {
        'booking': booking,
        'qr_url': qr_url,
        'description': description
    })

@login_required
def payment_confirm(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    if request.method == 'POST':
        booking.is_paid = True
        booking.payment_method = 'transfer'
        booking.save()
        messages.success(request, "Hệ thống đã ghi nhận thanh toán. Vui lòng chờ xác nhận từ lễ tân!")
    return redirect('my_bookings')

# --- 5. TÀI KHOẢN KHÁCH HÀNG ---
@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(user=request.user).select_related('room').prefetch_related('services').order_by('-created_at')
    return render(request, 'core/my_bookings.html', {'bookings': bookings})

@login_required
def cancel_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    if booking.status == 'pending':
        booking.delete()
        messages.success(request, "Đã hủy đơn thành công.")
    else:
        messages.error(request, "Không thể hủy đơn đã được xử lý.")
    return redirect('my_bookings')

# --- 6. QUẢN TRỊ (ADMIN DASHBOARD) ---
@user_passes_test(is_admin)
def admin_dashboard(request):
    # Tính doanh thu từ các đơn đã duyệt
    total_revenue = Booking.objects.filter(status='approved').aggregate(Sum('room__price'))['room__price__sum'] or 0
    pending_bookings = Booking.objects.filter(status='pending').select_related('user', 'room')
    status_stats = Booking.objects.values('status').annotate(total=Count('id'))
    
    context = {
        'total_revenue': total_revenue,
        'pending_count': pending_bookings.count(),
        'room_count': Room.objects.count(),
        'pending_bookings': pending_bookings,
        'booking_stats': {item['status']: item['total'] for item in status_stats}
    }
    return render(request, 'core/dashboard.html', context)

@user_passes_test(is_admin)
def manage_booking(request, pk, action):
    booking = get_object_or_404(Booking, pk=pk)
    if action == 'approve':
        booking.status = 'approved'
        booking.room.is_available = False
        booking.room.save()
    elif action == 'reject':
        booking.status = 'rejected'
        booking.room.is_available = True
        booking.room.save()
    booking.save()
    return redirect('admin_dashboard')

# --- 7. KHỞI TẠO HỆ THỐNG ---
def setup_database(request):
    try:
        call_command('migrate')
        if not User.objects.filter(is_superuser=True).exists():
            User.objects.create_superuser('admin_moi', 'admin@hotel.com', 'admin12345')
            return HttpResponse("Khởi tạo Admin thành công!")
        return HttpResponse("Hệ thống đã sẵn sàng.")
    except Exception as e:
        return HttpResponse(f"Lỗi: {e}")