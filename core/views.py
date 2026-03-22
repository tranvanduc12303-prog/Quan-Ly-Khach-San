import os
import json
import requests
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
from django.views.decorators.csrf import csrf_exempt

# Import các Model của dự án MyHotel
from .models import Room, Booking, Destination, Review, Service

# =================================================================
# 1. CẤU HÌNH HỆ THỐNG & TRỢ LÝ AI (GEMINI)
# =================================================================

# Lưu ý: Đức dán mã Token lấy từ mục API Gateway của Fchat vào đây
FC_TOKEN = "eyJ0eXAiOiJqd3QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOiIyMDI2LTAzLTIzVDA0OjEyOjU1KzA3MDAiLCJzaG9wX2lkIjoiNjljMDViNTY3MmJiMmU2OTRkMDVhZDY2In0.cDEzZornU1JE76dTlBn57WODyz1C90vDvDzNApPznsg"
FC_SHOP_ID = "69c05b672bb2e694d05ad66"

def get_ai_response(user_query):
    """
    Hàm xử lý logic AI: Nhận câu hỏi từ khách hàng, 
    truy vấn dữ liệu phòng thực tế và trả về câu trả lời thông minh.
    """
    api_key = os.environ.get('GEMINI_API_KEY')
    
    if not api_key:
        return "Chào bạn! MyHotel đã nhận được thông tin. Bạn cần tư vấn về phòng hay dịch vụ nào ạ?"
    
    try:
        genai.configure(api_key=api_key)
        model = genai.GenerativeModel('gemini-1.5-flash')
        
        # Lấy thông tin một vài phòng đang trống để AI tư vấn khách
        rooms_available = Room.objects.filter(is_available=True)[:3]
        room_list_info = ", ".join([f"Phòng {r.room_number} giá {r.price}VNĐ" for r in rooms_available])
        
        prompt_template = (
            f"Bạn là một nhân viên lễ tân chuyên nghiệp tại khách sạn MyHotel. "
            f"Danh sách phòng hiện đang còn trống: {room_list_info}. "
            f"Hãy trả lời khách hàng một cách lịch sự, ngắn gọn và hỗ trợ nhất. "
            f"Câu hỏi của khách hàng là: {user_query}"
        )
        
        response = model.generate_content(prompt_template)
        return response.text
    except Exception as e:
        print(f"Lỗi AI: {e}")
        return "Xin lỗi bạn, hệ thống tư vấn tự động đang bận. Vui lòng đợi trong giây lát, nhân viên sẽ hỗ trợ bạn ngay!"

def is_admin(user):
    """Hàm kiểm tra quyền quản trị viên"""
    return user.is_authenticated and user.is_staff

# =================================================================
# 2. HỆ THỐNG WEBHOOK FCHAT (KẾT NỐI AI VỚI FANPAGE)
# =================================================================

@csrf_exempt
def fchat_webhook(request):
    """
    Điểm tiếp nhận tin nhắn từ Fchat (Webhook). 
    Mỗi khi khách nhắn tin trên Fanpage, Fchat sẽ gửi dữ liệu tới đây.
    """
    if request.method == 'POST':
        try:
            # Đọc dữ liệu JSON gửi từ Fchat
            received_data = json.loads(request.body)
            customer_user_id = received_data.get('user_id')
            customer_message = received_data.get('message', '')

            if customer_user_id and customer_message:
                # Bước 1: Gửi tin nhắn khách hàng qua não bộ AI Gemini
                ai_answer = get_ai_response(customer_message)

                # Bước 2: Gửi câu trả lời của AI quay ngược lại cho khách qua API Fchat
                fchat_api_url = f"https://fchat.vn/api/send_message?token={FC_TOKEN}"
                payload_data = {
                    "user_id": customer_user_id,
                    "message": ai_answer
                }
                # Thực hiện lệnh gửi tin nhắn
                requests.post(fchat_api_url, json=payload_data)
                
            return HttpResponse("Dữ liệu đã được xử lý thành công", status=200)
        except Exception as error:
            return HttpResponse(f"Lỗi xử lý Webhook: {str(error)}", status=400)
            
    return HttpResponse("Chỉ chấp nhận phương thức POST", status=405)

# =================================================================
# 3. QUẢN LÝ TRANG CHỦ & TÌM KIẾM PHÒNG
# =================================================================

def home(request):
    """Hiển thị danh sách phòng và tìm kiếm phòng khách sạn"""
    search_query = request.GET.get('q', '').strip()
    all_destinations = Destination.objects.all()
    
    # Sắp xếp phòng trống lên đầu tiên
    all_rooms = Room.objects.all().order_by('-is_available', 'price')
    
    if search_query:
        all_rooms = all_rooms.filter(
            Q(room_number__icontains=search_query) | 
            Q(address__icontains=search_query) |
            Q(room_type__name__icontains=search_query)
        ).distinct()
        
    context_data = {
        'rooms': all_rooms, 
        'destinations': all_destinations, 
        'query': search_query,
        'room_count': all_rooms.count()
    }
    return render(request, 'core/home.html', context_data)

# =================================================================
# 4. CHI TIẾT PHÒNG, ĐẶT PHÒNG & ĐÁNH GIÁ
# =================================================================

def room_detail(request, pk):
    """Hiển thị chi tiết phòng và xử lý form đặt phòng/đánh giá"""
    selected_room = get_object_or_404(Room, pk=pk)
    room_reviews = selected_room.reviews.select_related('user').order_by('-created_at')
    available_services = Service.objects.all()
    
    if request.method == 'POST':
        # Trường hợp 1: Người dùng thực hiện đặt phòng
        if 'book_room' in request.POST:
            if not request.user.is_authenticated:
                messages.warning(request, "Vui lòng đăng nhập để có thể đặt phòng này.")
                return redirect('login')
            
            check_in_date = request.POST.get('check_in')
            check_out_date = request.POST.get('check_out')
            
            try:
                converted_in = datetime.strptime(check_in_date, '%Y-%m-%d').date()
                converted_out = datetime.strptime(check_out_date, '%Y-%m-%d').date()
                
                if converted_out <= converted_in:
                    messages.error(request, "Ngày trả phòng không được phép trước hoặc bằng ngày nhận phòng.")
                else:
                    new_booking = Booking.objects.create(
                        user=request.user, 
                        room=selected_room, 
                        check_in=converted_in, 
                        check_out=converted_out, 
                        status='pending'
                    )
                    messages.success(request, "Yêu cầu đặt phòng của bạn đã được gửi thành công!")
                    return redirect('payment_page', booking_id=new_booking.id)
            except (ValueError, TypeError):
                messages.error(request, "Định dạng ngày tháng không hợp lệ.")

        # Trường hợp 2: Người dùng gửi đánh giá phòng
        elif 'submit_review' in request.POST:
            if request.user.is_authenticated:
                review_comment = request.POST.get('comment', '').strip()
                review_rating = request.POST.get('rating', 5)
                if review_comment:
                    Review.objects.create(
                        room=selected_room, 
                        user=request.user, 
                        rating=int(review_rating), 
                        comment=review_comment
                    )
                    messages.success(request, "Cảm ơn bạn đã gửi phản hồi cho khách sạn!")
                return redirect('room_detail', pk=pk)

    return render(request, 'core/room_detail.html', {
        'room': selected_room, 
        'reviews': room_reviews, 
        'services': available_services
    })

# =================================================================
# 5. HỆ THỐNG THANH TOÁN VIETQR
# =================================================================

@login_required
def payment_page(request, booking_id):
    """Tạo mã QR thanh toán ngân hàng tự động cho đơn hàng"""
    booking_info = get_object_or_404(Booking, id=booking_id, user=request.user)
    
    # Cấu hình tài khoản ngân hàng nhận tiền
    target_bank = "MB" 
    target_account = "0987654321" 
    target_name = "KHACH SAN MYHOTEL"
    
    total_amount = int(booking_info.room.price) if booking_info.room.price else 0
    payment_desc = f"THANH TOAN DON HANG MYHOTEL{booking_info.id}"
    
    # Tạo URL ảnh QR dựa theo chuẩn VietQR
    qr_code_url = (
        f"https://img.vietqr.io/image/{target_bank}-{target_account}-compact2.png"
        f"?amount={total_amount}&addInfo={payment_desc}&accountName={target_name}"
    )
    
    return render(request, 'core/payment.html', {
        'booking': booking_info, 
        'qr_url': qr_code_url,
        'total_price': total_amount
    })

# =================================================================
# 6. TRANG CÁ NHÂN & QUẢN LÝ LỊCH SỬ
# =================================================================

@login_required
def profile(request):
    """Hiển thị thông tin hồ sơ và các đơn hàng của khách"""
    user_bookings = Booking.objects.filter(user=request.user).select_related('room').order_by('-id')
    stats_data = {
        'total_bookings': user_bookings.count(),
        'approved_bookings': user_bookings.filter(status='approved').count(),
        'pending_bookings': user_bookings.filter(status='pending').count(),
    }
    return render(request, 'core/profile.html', {
        'user': request.user, 
        'bookings': user_bookings, 
        'stats': stats_data
    })

@login_required
def edit_profile(request):
    """Cập nhật thông tin cá nhân của người dùng"""
    if request.method == 'POST':
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.email = request.POST.get('email', '')
        request.user.save()
        messages.success(request, "Cập nhật thông tin cá nhân thành công!")
        return redirect('profile')
    return render(request, 'core/edit_profile.html')

@login_required
def cancel_booking(request, pk):
    """Khách hàng tự hủy đơn đặt phòng khi đang chờ duyệt"""
    booking_to_cancel = get_object_or_404(Booking, pk=pk, user=request.user)
    if booking_to_cancel.status == 'pending':
        booking_to_cancel.delete()
        messages.success(request, "Đã hủy đơn đặt phòng thành công.")
    else:
        messages.error(request, "Không thể hủy đơn đã được xử lý.")
    return redirect('profile')

# =================================================================
# 7. QUẢN TRỊ VIÊN (ADMIN DASHBOARD)
# =================================================================

@user_passes_test(is_admin)
def admin_dashboard(request):
    """Trang tổng quan dành cho quản lý khách sạn"""
    total_revenue = Booking.objects.filter(
        status__in=['approved', 'completed']
    ).aggregate(total_sum=Sum('room__price'))['total_sum'] or 0
    
    pending_approvals = Booking.objects.filter(status='pending').select_related('user', 'room').order_by('-id')
    
    # Dữ liệu phục vụ biểu đồ thống kê
    booking_counts = Booking.objects.values('status').annotate(count_id=Count('id'))
    
    return render(request, 'core/dashboard.html', {
        'revenue': total_revenue,
        'pending_list': pending_approvals,
        'room_count': Room.objects.count(),
        'user_count': User.objects.count(),
        'chart_data': list(booking_counts)
    })

@user_passes_test(is_admin)
def manage_booking(request, pk, action):
    """Phê duyệt hoặc từ chối đặt phòng từ phía Admin"""
    booking_to_manage = get_object_or_404(Booking, pk=pk)
    
    if action == 'approve':
        booking_to_manage.status = 'approved'
        booking_to_manage.room.is_available = False # Tạm khóa phòng khi đã duyệt
    elif action == 'reject':
        booking_to_manage.status = 'rejected'
        booking_to_manage.room.is_available = True
        
    booking_to_manage.room.save()
    booking_to_manage.save()
    messages.info(request, f"Đã cập nhật đơn hàng mã số #{booking_to_manage.id}")
    return redirect('admin_dashboard')

# =================================================================
# 8. TIỆN ÍCH HỆ THỐNG & ĐĂNG KÝ
# =================================================================

def register(request):
    """Đăng ký tài khoản người dùng mới"""
    if request.method == 'POST':
        form_instance = UserCreationForm(request.POST)
        if form_instance.is_valid():
            form_instance.save()
            messages.success(request, "Đăng ký thành công! Vui lòng đăng nhập vào hệ thống.")
            return redirect('login')
    else:
        form_instance = UserCreationForm()
    return render(request, 'registration/register.html', {'form': form_instance})

def setup_database(request):
    """Lệnh khẩn cấp để khởi tạo Database trên Render (Migration + Superuser)"""
    try:
        call_command('migrate')
        if not User.objects.filter(username='admin_moi').exists():
            User.objects.create_superuser('admin_moi', 'admin@hotel.com', 'admin12345')
            return HttpResponse("Khởi tạo Database và Admin thành công!")
        return HttpResponse("Hệ thống Database đã hoạt động bình thường.")
    except Exception as error:
        return HttpResponse(f"Lỗi khi thiết lập Database: {str(error)}")

def ai_assistant(request):
    """View xử lý Chatbox trực tiếp trên giao diện Website"""
    incoming_query = request.GET.get('message', '').strip()
    if not incoming_query:
        return JsonResponse({'reply': "Chào bạn! MyHotel có thể giúp gì cho bạn hôm nay?"})
    
    return JsonResponse({'reply': get_ai_response(incoming_query)})

# HẾT FILE VIEWS.PY