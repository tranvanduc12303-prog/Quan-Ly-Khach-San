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

# --- 1. HỆ THỐNG AI TƯ VẤN ---
def ai_assistant(request):
    user_message = request.GET.get('message', '').strip()
    if not user_message:
        return JsonResponse({'reply': "Chào bạn! MyHotel có thể giúp gì cho bạn?"})

    api_key = os.environ.get('GROQ_API_KEY')
    if not api_key:
        return JsonResponse({'reply': "Chatbot chưa được cấu hình API Key, vui lòng liên hệ Admin."})

    try:
        client = Groq(api_key=api_key.strip())
        available_rooms = Room.objects.filter(is_available=True).select_related('room_type')[:3]
        room_info = [f"Phòng {r.room_number} ({r.room_type.name}) giá {int(r.price):,} VNĐ" for r in available_rooms]
        context = "Thông tin phòng trống: " + ", ".join(room_info) if room_info else "Hết phòng trống."

        prompt = f"Bạn là lễ tân MyHotel. {context}. Trả lời ngắn gọn, lịch sự khách hỏi: {user_message}"
        
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192",
            temperature=0.7,
        )
        return JsonResponse({'reply': completion.choices[0].message.content.strip()})
    except Exception as e:
        return JsonResponse({'reply': "Vui lòng gọi hotline 1900xxxx để được hỗ trợ nhé!"})

# --- 2. TRANG CHỦ ---
def home(request):
    query = request.GET.get('q', '').strip()
    destinations = Destination.objects.all()
    rooms = Room.objects.select_related('room_type').all().order_by('-is_available', 'price')
    
    if query:
        rooms = rooms.filter(
            Q(room_number__icontains=query) | Q(address__icontains=query) |
            Q(room_type__name__icontains=query) | Q(description__icontains=query)
        ).distinct()

    return render(request, 'core/home.html', {'rooms': rooms, 'destinations': destinations, 'query': query})

# --- 3. CHI TIẾT PHÒNG & ĐÁNH GIÁ ---
def room_detail(request, pk):
    room = get_object_or_404(Room, pk=pk)
    reviews = room.reviews.select_related('user').order_by('-created_at')
    services = Service.objects.all()

    if request.method == 'POST':
        # Xử lý Đặt phòng
        if 'book_room' in request.POST:
            if not request.user.is_authenticated:
                messages.warning(request, "Vui lòng đăng nhập để đặt phòng.")
                return redirect('login')
            try:
                check_in = datetime.strptime(request.POST.get('check_in'), '%Y-%m-%d').date()
                check_out = datetime.strptime(request.POST.get('check_out'), '%Y-%m-%d').date()
                if check_out <= check_in:
                    messages.error(request, "Ngày trả phòng không hợp lệ.")
                else:
                    booking = Booking.objects.create(
                        user=request.user, room=room, check_in=check_in, 
                        check_out=check_out, status='pending'
                    )
                    booking.services.set(request.POST.getlist('services'))
                    messages.success(request, "Đặt phòng thành công!")
                    return redirect('payment_page', booking_id=booking.id)
            except:
                messages.error(request, "Định dạng ngày không đúng.")

        # Xử lý Gửi đánh giá (Review)
        elif 'submit_review' in request.POST:
            if not request.user.is_authenticated:
                messages.error(request, "Vui lòng đăng nhập.")
            else:
                Review.objects.create(
                    room=room, user=request.user,
                    rating=int(request.POST.get('rating', 5)),
                    comment=request.POST.get('comment', '')
                )
                messages.success(request, "Cảm ơn bạn đã đánh giá!")
                return redirect('room_detail', pk=pk)

    return render(request, 'core/room_detail.html', {'room': room, 'reviews': reviews, 'services': services})

# --- 4. THANH TOÁN ---
@login_required
def payment_page(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    BANK_ID, ACCOUNT_NO, ACCOUNT_NAME = "MB", "0987654321", "MYHOTEL"
    amount = int(booking.total_price)
    qr_url = f"https://img.vietqr.io/image/{BANK_ID}-{ACCOUNT_NO}-compact2.png?amount={amount}&addInfo=MYHOTEL{booking.id}&accountName={ACCOUNT_NAME}"
    return render(request, 'core/payment.html', {'booking': booking, 'qr_url': qr_url})

# --- 5. ADMIN DASHBOARD (BIỂU ĐỒ) ---
@user_passes_test(is_admin)
def admin_dashboard(request):
    # Dữ liệu cho biểu đồ trạng thái
    status_stats = Booking.objects.values('status').annotate(total=Count('id'))
    booking_labels = [s['status'].capitalize() for s in status_stats]
    booking_data = [s['total'] for s in status_stats]

    # Dữ liệu cho biểu đồ khu vực (Sử dụng địa chỉ phòng)
    room_stats = Room.objects.values('address').annotate(total=Count('id'))
    room_labels = [r['address'] for r in room_stats]
    room_data = [r['total'] for r in room_stats]

    pending_bookings = Booking.objects.filter(status='pending').select_related('user', 'room')

    context = {
        'total_revenue': Booking.objects.filter(Q(status='approved') | Q(is_paid=True)).aggregate(Sum('room__price'))['room__price__sum'] or 0,
        'pending_bookings': pending_bookings,
        'booking_labels': booking_labels,
        'booking_data': booking_data,
        'room_labels': room_labels,
        'room_data': room_data,
    }
    return render(request, 'core/dashboard.html', context)

# --- CÁC HÀM CƠ BẢN KHÁC ---
@login_required
def my_bookings(request):
    return render(request, 'core/my_bookings.html', {'bookings': Booking.objects.filter(user=request.user).order_by('-created_at')})

@user_passes_test(is_admin)
def manage_booking(request, pk, action):
    booking = get_object_or_404(Booking, pk=pk)
    if action == 'approve':
        booking.status, booking.room.is_available = 'approved', False
    elif action == 'reject':
        booking.status = 'rejected'
    booking.room.save()
    booking.save()
    return redirect('admin_dashboard')

def setup_database(request):
    call_command('migrate')
    if not User.objects.filter(username='admin_moi').exists():
        User.objects.create_superuser('admin_moi', 'admin@hotel.com', 'admin12345')
    return HttpResponse("Hệ thống đã sẵn sàng!")