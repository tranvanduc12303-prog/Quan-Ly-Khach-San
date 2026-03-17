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
    if not api_key:
        return JsonResponse({'reply': "Chatbot chưa được cấu hình API Key, vui lòng liên hệ Admin."})

    try:
        client = Groq(api_key=api_key.strip())
        # Lấy thông tin phòng thực tế để AI trả lời chính xác
        available_rooms = Room.objects.filter(is_available=True).select_related('room_type')[:3]
        room_info = [f"Phòng {r.room_number} ({r.room_type.name}) giá {int(r.price):,} VNĐ tại {r.address}" for r in available_rooms]
        context = "Thông tin phòng trống hiện có: " + ", ".join(room_info) if room_info else "Hiện tại khách sạn đã hết phòng trống."

        prompt = f"Bạn là nhân viên lễ tân ảo của khách sạn MyHotel. {context}. Hãy trả lời bằng tiếng Việt, phong cách lịch sự, thân thiện và ngắn gọn. Nếu khách hỏi đặt phòng, hãy hướng dẫn họ chọn phòng trên web. Khách hỏi: {user_message}"
        
        completion = client.chat.completions.create(
            messages=[{"role": "user", "content": prompt}],
            model="llama3-8b-8192",
            temperature=0.7,
        )
        return JsonResponse({'reply': completion.choices[0].message.content.strip()})
    except Exception as e:
        print(f"AI Error: {e}")
        return JsonResponse({'reply': "Hiện tại mình đang bận một chút, bạn vui lòng gọi hotline 1900xxxx để được hỗ trợ nhanh nhất nhé!"})

# --- 2. TRANG CHỦ & TÌM KIẾM ---
def home(request):
    query = request.GET.get('q', '').strip()
    destinations = Destination.objects.all()
    # Hiển thị phòng trống lên trước, phòng đã đặt xuống sau
    rooms = Room.objects.select_related('room_type').all().order_by('-is_available', 'price')
    
    if query:
        rooms = rooms.filter(
            Q(room_number__icontains=query) | 
            Q(address__icontains=query) |
            Q(room_type__name__icontains=query) |
            Q(description__icontains=query)
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
    services = Service.objects.all() # Lấy danh sách dịch vụ để khách chọn

    if request.method == 'POST' and 'book_room' in request.POST:
        if not request.user.is_authenticated:
            messages.warning(request, "Vui lòng đăng nhập để thực hiện đặt phòng.")
            return redirect('login')
        
        try:
            check_in_str = request.POST.get('check_in')
            check_out_str = request.POST.get('check_out')
            check_in = datetime.strptime(check_in_str, '%Y-%m-%d').date()
            check_out = datetime.strptime(check_out_str, '%Y-%m-%d').date()

            if check_out <= check_in:
                messages.error(request, "Lỗi: Ngày trả phòng phải sau ngày nhận phòng.")
            elif check_in < timezone.now().date():
                messages.error(request, "Lỗi: Không thể đặt phòng cho ngày đã qua.")
            elif not room.is_available:
                messages.error(request, "Rất tiếc, phòng này vừa có khách khác đặt.")
            else:
                # Tạo đơn đặt phòng
                booking = Booking.objects.create(
                    user=request.user, 
                    room=room, 
                    check_in=check_in, 
                    check_out=check_out, 
                    status='pending'
                )
                
                # Xử lý dịch vụ đi kèm (ManyToMany)
                selected_services = request.POST.getlist('services')
                if selected_services:
                    booking.services.set(selected_services)
                    booking.save() # Save lại để tính toán lại total_price nếu cần

                messages.success(request, "Đã tạo đơn thành công! Vui lòng hoàn tất thanh toán.")
                return redirect('payment_page', booking_id=booking.id)
        except ValueError:
            messages.error(request, "Vui lòng nhập đúng định dạng ngày tháng.")
        except Exception as e:
            messages.error(request, f"Có lỗi xảy ra: {e}")

    return render(request, 'core/room_detail.html', {
        'room': room, 
        'reviews': reviews, 
        'services': services
    })

# --- 4. THANH TOÁN (VIETQR) ---
@login_required
def payment_page(request, booking_id):
    booking = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    # THÔNG TIN TÀI KHOẢN NHẬN TIỀN (Bạn hãy sửa lại theo ý mình)
    BANK_ID = "MB" # Ví dụ: MB, VCB, ICB
    ACCOUNT_NO = "0987654321" 
    ACCOUNT_NAME = "KHACH SAN MYHOTEL"
    
    # Sử dụng property total_price từ model để lấy số tiền chính xác
    amount = int(booking.total_price)
    description = f"MYHOTEL{booking.id}"
    
    # URL VietQR: compact2 là mẫu QR nhỏ gọn kèm logo ngân hàng
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
        booking.payment_method = 'transfer' # Ghi nhận thanh toán chuyển khoản
        booking.save()
        messages.success(request, "Cảm ơn bạn! Hệ thống đã ghi nhận thanh toán và đang đợi lễ tân xác nhận.")
    return redirect('my_bookings')

# --- 5. TÀI KHOẢN KHÁCH HÀNG ---
@login_required
def my_bookings(request):
    bookings = Booking.objects.filter(user=request.user).select_related('room', 'room__room_type').prefetch_related('services').order_by('-created_at')
    return render(request, 'core/my_bookings.html', {'bookings': bookings})

@login_required
def cancel_booking(request, pk):
    booking = get_object_or_404(Booking, pk=pk, user=request.user)
    if booking.status == 'pending':
        booking.delete()
        messages.success(request, "Đã hủy đơn đặt phòng.")
    else:
        messages.error(request, "Đơn hàng đã được xử lý, không thể tự hủy. Vui lòng liên hệ khách sạn.")
    return redirect('my_bookings')

# --- 6. QUẢN TRỊ (ADMIN DASHBOARD) ---
@user_passes_test(is_admin)
def admin_dashboard(request):
    # Thống kê doanh thu thực tế từ các đơn đã thanh toán HOẶC đã duyệt
    total_revenue = Booking.objects.filter(Q(status='approved') | Q(is_paid=True)).aggregate(total=Sum('room__price'))['total'] or 0
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
        booking.room.is_available = False # Đánh dấu phòng đã có người
        booking.room.save()
    elif action == 'reject':
        booking.status = 'rejected'
        booking.room.is_available = True
        booking.room.save()
    elif action == 'complete':
        booking.status = 'completed'
        booking.room.is_available = True # Khách trả phòng -> Phòng trống lại
        booking.room.save()
        
    booking.save()
    messages.info(request, f"Đã cập nhật đơn hàng #{booking.id}")
    return redirect('admin_dashboard')

# --- 7. KHỞI TẠO HỆ THỐNG (CHỈ DÙNG KHI MỚI DEPLOY) ---
def setup_database(request):
    try:
        # Tự động chạy migrate
        call_command('migrate')
        # Tạo tài khoản admin mặc định nếu chưa có
        if not User.objects.filter(username='admin_moi').exists():
            User.objects.create_superuser('admin_moi', 'admin@hotel.com', 'admin12345')
            return HttpResponse("Khởi tạo Admin (admin_moi / admin12345) thành công!")
        return HttpResponse("Hệ thống đã ổn định.")
    except Exception as e:
        return HttpResponse(f"Lỗi khi cấu hình: {e}")