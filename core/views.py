import os
import json
import requests
from datetime import datetime
from django.conf import settings
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.models import User
from django.contrib.auth.forms import UserCreationForm
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Q, Count, Sum, Avg
from django.http import JsonResponse, HttpResponse
from django.core.management import call_command
from django.views.decorators.csrf import csrf_exempt

# Import các Model của dự án MyHotel
from .models import Room, Booking, Destination, Review, Service, UserProfile
from .forms import RoomImageForm

# =================================================================
# 1. CẤU HÌNH HỆ THỐNG & TRỢ LÝ AI (GEMINI)
# =================================================================

# Lưu ý: Đức dán mã Token lấy từ mục API Gateway của Fchat vào đây
FC_TOKEN = "eyJ0eXAiOiJqd3QiLCJhbGciOiJIUzI1NiJ9.eyJpYXQiOiIyMDI2LTAzLTIzVDA0OjEyOjU1KzA3MDAiLCJzaG9wX2lkIjoiNjljMDViNTY3MmJiMmU2OTRkMDVhZDY2In0.cDEzZornU1JE76dTlBn57WODyz1C90vDvDzNApPznsg"
FC_SHOP_ID = "69c05b672bb2e694d05ad66"

def get_room_response(user_query):
    """Trả về câu trả lời cố định cho các câu hỏi liên quan phòng và khách sạn."""
    q = user_query.lower()

    # Câu hỏi về địa chỉ/vị trí
    if any(phrase in q for phrase in ['địa chỉ', 'ở đâu', 'thành phố', 'khu vực', 'tỉnh', 'vị trí', 'nơi ở', 'tọa lạc', 'khu đất', 'miền', 'quận', 'huyện']):
        available_rooms = Room.objects.filter(is_available=True)
        if available_rooms.exists():
            addresses = set(room.address for room in available_rooms)
            address_list = ", ".join(addresses)
            return f"✨ MyHotel hiện có phòng tại: {address_list}. Bạn muốn tìm phòng ở khu vực cụ thể nào không?"
        return "Hiện tại không có phòng trống. Bạn vui lòng liên hệ để được hỗ trợ."

    # Câu hỏi về đặt phòng
    if any(phrase in q for phrase in ['đặt phòng', 'cách đặt', 'làm sao đặt', 'muốn đặt', 'đặt phòng như thế nào', 'quy trình đặt', 'cách để đặt phòng']):
        return "📋 Quy trình đặt phòng:\n1. Chọn phòng bạn yêu thích\n2. Chọn ngày nhận/trả phòng\n3. Chọn dịch vụ (nếu cần)\n4. Nhấn 'Đặt phòng'\n5. Tiến hành thanh toán\n6. Nhận xác nhận từ MyHotel. Bạn cần tư vấn thêm không?"

    # Câu hỏi về hủy phòng
    if any(phrase in q for phrase in ['hủy', 'huỷ', 'bỏ phòng', 'hủy đặt', 'hủy phòng', 'không muốn đặt nữa', 'huỷ bỏ đặt phòng']):
        return "🔄 Hủy phòng:\n- Nếu chưa duyệt: Vào trang cá nhân > Đơn đặt phòng > Hủy\n- Nếu đã duyệt: Liên hệ lễ tân để được xử lý\n- Hoàn tiền sẽ được gửi trong 3-5 ngày làm việc."

    # Câu hỏi về liên hệ/hỗ trợ
    if any(phrase in q for phrase in ['liên hệ', 'hỗ trợ', 'hotline', 'số điện thoại', 'email', 'facebook', 'hỏi gì', 'cần giúp', '24/7', 'hỗ trợ khách hàng']):
        return "📞 Liên hệ MyHotel:\n• Hotline: 1900 XXXX (24/7)\n• Email: support@myhotel.vn\n• Facebook: MyHotel Official\n• Website: www.myhotel.vn\n\nChúng tôi luôn sẵn sàng hỗ trợ bạn!"

    # Câu hỏi về thanh toán
    if any(phrase in q for phrase in ['thanh toán', 'payment', 'cách thanh toán', 'trả tiền', 'được thanh toán', 'hình thức thanh', 'thẻ', 'ngân hàng', 'tiền mặt', 'chấp nhận']):
        return "💳 Phương thức thanh toán:\nMyHotel chấp nhận:\n• Thẻ tín dụng (Visa, Mastercard)\n• Chuyển khoản ngân hàng\n• Ví điện tử (ZaloPay, Momo)\n• Tiền mặt tại quầy\n\nLựa chọn nào phù hợp với bạn?"

    # Câu hỏi về giảm giá/khuyến mãi
    if any(phrase in q for phrase in ['giảm giá', 'khuyến mãi', 'discount', 'sale', 'giá rẻ', 'ưu đãi', 'mã giảm', 'promo', 'deal']):
        return "🎉 Ưu đãi & khuyến mãi:\nMyHotel thường xuyên có:\n• Giảm giá cho đặt trước\n• Combo package tiết kiệm\n• Ưu đãi khách hàng thân thiết\n• Mã khuyến mãi mùa lễ\n\nBạn hãy liên hệ để nhận ưu đãi tốt nhất!"

    # Câu hỏi về khoảng cách/vận chuyển
    if any(phrase in q for phrase in ['cách bao xa', 'khoảng cách', 'gần', 'xa', 'sân bay', 'ga tàu', 'giao thông', 'đi lại', 'transport']):
        return "🚗 Vị trí & giao thông:\nMyHotel có vị trí thuận lợi:\n• Gần sân bay/ga tàu\n• Dễ dàng di chuyển\n• Gần các điểm du lịch\n• Dịch vụ xe đưa đón có sẵn\n\nBạn cần chi tiết vị trí cụ thể nào?"

    # Kiểm tra nếu không liên quan đến phòng
    room_keywords = ['phòng', 'room', 'phong', 'khách sạn', 'hotel', 'myhotel']
    if not any(word in q for word in room_keywords):
        return "Xin chào! 👋 Tôi là trợ lý ảo của MyHotel. Tôi có thể giúp bạn tư vấn về phòng, giá cả, dịch vụ và tiện ích. Bạn có câu hỏi gì không?"

    available_rooms = Room.objects.filter(is_available=True)

    # Câu hỏi về phòng trống
    if any(phrase in q for phrase in ['còn phòng', 'phòng trống', 'còn trống', 'phòng còn', 'available', 'phòng nào còn', 'phòng nào trống', 'có phòng không', 'phòng còn khả dụng']):
        if not available_rooms.exists():
            return "😔 Hiện tại MyHotel đang tạm hết phòng trống. Bạn vui lòng thử lại sau hoặc liên hệ trực tiếp để được hỗ trợ."
        rooms = available_rooms[:5]  # Hiển thị tối đa 5 phòng
        room_list = "\n".join([f"  • Phòng {r.room_number} ({r.room_type.name}) - {r.address} - {int(r.price):,} VNĐ/đêm" for r in rooms])
        return f"✅ Phòng trống hiện có:\n{room_list}\n\nBạn muốn chọn phòng nào?"

    # Câu hỏi về giá phòng
    if any(phrase in q for phrase in ['giá', 'bao nhiêu', 'chi phí', 'tiền', 'giá tiền', 'giá cả', 'mức giá', 'chi phí phòng', 'giá phòng bao nhiêu', 'phòng bao nhiêu tiền', 'rẻ nhất', 'đắt nhất']):
        if available_rooms.exists():
            cheapest = available_rooms.order_by('price').first()
            most_expensive = available_rooms.order_by('-price').first()
            avg_price = int(available_rooms.aggregate(avg=Avg('price'))['avg'] or 0)
            return f"💰 Giá phòng tại MyHotel:\n• Giá thấp nhất: {int(cheapest.price):,} VNĐ/đêm (Phòng {cheapest.room_number})\n• Giá cao nhất: {int(most_expensive.price):,} VNĐ/đêm\n• Giá trung bình: {avg_price:,} VNĐ/đêm\n\nBạn có muốn tìm phòng theo tầm giá cụ thể không?"
        return "Hiện không có phòng trống để báo giá. Bạn thử hỏi lại sau nhé."

    # Câu hỏi về loại phòng
    if any(phrase in q for phrase in ['loại phòng', 'danh sách', 'có những phòng', 'phòng nào', 'phòng loại', 'phòng gì', 'các loại phòng', 'phòng khác nhau', 'có những loại']):
        room_types = Room.objects.values_list('room_type__name', flat=True).distinct()
        room_types = [rt for rt in room_types if rt]
        if room_types:
            type_list = ", ".join(room_types)
            return f"🛏️ MyHotel cung cấp các loại phòng: {type_list}. Bạn muốn tìm phòng loại nào?"
        return "Hiện tại hệ thống đang cập nhật các loại phòng. Bạn vui lòng hỏi lại sau nhé."

    # Câu hỏi về số lượng phòng
    if any(phrase in q for phrase in ['bao nhiêu phòng', 'số lượng phòng', 'tổng phòng', 'tổng cộng', 'có bao nhiêu phòng', 'phòng bao nhiêu cái']):
        total_rooms = Room.objects.count()
        available_count = available_rooms.count()
        return f"📊 Thông tin phòng tại MyHotel:\n• Tổng số phòng: {total_rooms} phòng\n• Phòng còn trống: {available_count} phòng\n• Phòng đã đặt: {total_rooms - available_count} phòng"

    # Câu hỏi về tiện ích/dịch vụ
    if any(phrase in q for phrase in ['dịch vụ', 'service', 'tiện ích', 'có gì', 'phòng có', 'được cung cấp', 'bao gồm', 'gồm có', 'đi kèm', 'trang bị', 'thiết bị', 'wifi', 'điều hòa', 'tivi', 'phòng tắm', 'bếp']):
        services = Service.objects.all()
        if services.exists():
            service_list = "\n".join([f"  • {s.name}: {int(s.price):,} VNĐ" for s in services])
            return f"🎁 Dịch vụ & tiện ích tại MyHotel:\n{service_list}\n\nBạn có thể chọn dịch vụ khi đặt phòng."
        return "✨ MyHotel cung cấp nhiều dịch vụ tiện ích như: WiFi miễn phí, điều hòa, tivi, phòng tắm hiện đại, v.v. Bạn muốn tìm hiểu chi tiết không?"

    # Câu hỏi về đánh giá/review
    if any(phrase in q for phrase in ['đánh giá', 'review', 'phản hồi', 'sao', 'rating', 'nhận xét', 'comment', 'ý kiến', 'phòng tốt', 'phòng xấu']):
        rooms_with_reviews = Room.objects.filter(reviews__isnull=False).distinct()
        if rooms_with_reviews.exists():
            best_room = max(rooms_with_reviews, key=lambda r: r.average_rating if r.average_rating else 0)
            return f"⭐ Đánh giá từ khách hàng:\n• Phòng được yêu thích nhất: Phòng {best_room.room_number} - {best_room.average_rating}/5 sao\n\nBạn có thể xem đánh giá chi tiết của từng phòng trên trang web."
        return "⭐ Các phòng của MyHotel đều nhận được phản hồi tích cực từ khách hàng. Bạn có thể xem đánh giá chi tiết trên trang của từng phòng."

    # Câu hỏi về chi tiết phòng
    if any(phrase in q for phrase in ['chi tiết', 'thông tin', 'mô tả', 'như thế nào', 'ra sao', 'tìm hiểu', 'biết thêm', 'hình ảnh', 'ảnh']):
        return "📸 Thông tin chi tiết phòng:\nBạn có thể xem chi tiết từng phòng trên trang chủ hoặc trang phòng cụ thể:\n• Ảnh phòng chất lượng cao\n• Giá tiền chi tiết\n• Địa chỉ & vị trí\n• Đánh giá & nhận xét từ khách hàng\n• Danh sách dịch vụ kèm theo"

    # Câu hỏi về phòng đôi/cặp
    if any(phrase in q for phrase in ['phòng đôi', 'phòng cặp', 'phòng 2 người', 'phòng vợ chồng', 'phòng tình nhân', 'phòng honeymoon']):
        return "💑 Phòng cho cặp đôi:\nMyHotel có nhiều phòng đôi với các trang thiết bị hiện đại, thoải mái và lãng mạn. Giá từ [giá thấp] đến [giá cao] VNĐ/đêm.\n\nBạn muốn xem các phòng đôi nào?"

    # Câu hỏi về phòng gia đình/nhóm
    if any(phrase in q for phrase in ['phòng gia đình', 'phòng nhóm', 'phòng 4 người', 'phòng 3 người', 'phòng tập thể', 'phòng đoàn']):
        return "👨‍👩‍👧‍👦 Phòng gia đình/nhóm:\nMyHotel cung cấp phòng rộng rãi cho gia đình hoặc nhóm bạn:\n• Phòng 3 người: Phù hợp cho gia đình nhỏ\n• Phòng 4+ người: Ideal cho nhóm bạn\n\nĐặc biệt tiết kiệm khi đặt từ 3 đêm trở lên!"

    # Câu hỏi về phòng một người
    if any(phrase in q for phrase in ['phòng một', 'phòng đơn', 'phòng 1 người', 'phòng solo', 'phòng riêng']):
        return "🚶 Phòng một người:\nMyHotel có nhiều phòng đơn gọn gàng, tiện lợi cho du khách độc hành:\n• Giường đơn hoặc giường đôi\n• Hệ thống WiFi mạnh mẽ\n• Giá cạnh tranh từ [giá] VNĐ/đêm\n\nPerfect cho những ai thích độc lập!"

    # Câu hỏi về nhân viên/lễ tân
    if any(phrase in q for phrase in ['nhân viên', 'lễ tân', 'staff', 'quản lý', 'hỏi người', 'nói chuyện với']):
        return "👥 Đội ngũ nhân viên MyHotel:\nChúng tôi có đội ngũ nhân viên thân thiện, chuyên nghiệp sẵn sàng:\n• Hỗ trợ 24/7\n• Tư vấn chi tiết\n• Xử lý các yêu cầu đặc biệt\n\nHãy gọi hotline để nói chuyện trực tiếp với lễ tân!"

    # Nếu không khớp với bất kỳ câu hỏi nào
    return "👋 Chào bạn! Tôi có thể giúp bạn:\n• Tìm phòng trống phù hợp\n• Báo giá chi tiết\n• Tư vấn loại phòng\n• Hỏi về dịch vụ & tiện ích\n• Hướng dẫn đặt phòng\n\nBạn có câu hỏi cụ thể nào không? 😊"


def get_ai_response(user_query):
    """
    Hàm xử lý logic AI: Nhận câu hỏi từ khách hàng, 
    truy vấn dữ liệu phòng thực tế và trả về câu trả lời thông minh.
    """
    room_response = get_room_response(user_query)
    if room_response:
        return room_response

    # Nếu không khớp với bất kỳ câu hỏi nào, trả lời mặc định
    return "Chào bạn! MyHotel đã nhận được thông tin. Bạn cần tư vấn về phòng hay dịch vụ nào ạ?"


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
    all_destinations = Destination.objects.filter(is_featured=True)
    
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
    # Lấy danh sách đơn hàng của riêng người dùng đang đăng nhập
    user_bookings = Booking.objects.filter(user=request.user).select_related('room').order_by('-id')
    
    # Tính toán các con số
    total_bookings = user_bookings.count()
    # Bao gồm cả 'approved' (Xác nhận) và 'completed' (Thành công) cho khớp với thực tế
    approved_bookings = user_bookings.filter(status__in=['approved', 'completed']).count()
    pending_bookings_count = user_bookings.filter(status='pending').count()

    profile, _ = UserProfile.objects.get_or_create(user=request.user)
    context = {
        'user': request.user,
        'bookings': user_bookings,
        # TRUYỀN TRỰC TIẾN BIẾN RA NGOÀI ĐỂ KHỚP VỚI HTML
        'total_bookings': total_bookings,
        'approved_bookings': approved_bookings,
        'pending_bookings_count': pending_bookings_count,
        'profile': profile,
    }
    
    return render(request, 'core/profile.html', context)

@login_required
def edit_profile(request):
    """Cập nhật thông tin cá nhân của người dùng"""
    if request.method == 'POST':
        # Cập nhật thông tin User cơ bản
        request.user.first_name = request.POST.get('first_name', '')
        request.user.last_name = request.POST.get('last_name', '')
        request.user.email = request.POST.get('email', '')
        request.user.save()

        # Cập nhật thông tin Profile mở rộng
        profile, created = UserProfile.objects.get_or_create(user=request.user)
        profile.full_name = request.POST.get('full_name', '')
        profile.age = request.POST.get('age', '') or None
        profile.hometown = request.POST.get('hometown', '')
        profile.birth_year = request.POST.get('birth_year', '') or None
        profile.phone_number = request.POST.get('phone_number', '')
        profile.email = request.POST.get('profile_email', '')
        profile.save()

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
@login_required
def my_bookings(request):
    """Hiển thị danh sách tất cả phòng khách đã đặt (đầy đủ)."""
    bookings = Booking.objects.filter(user=request.user).select_related('room').order_by('-id')
    return render(request, 'core/my_bookings.html', {'bookings': bookings})

# =================================================================
# 7. QUẢN TRỊ VIÊN (ADMIN DASHBOARD)
# =================================================================

@user_passes_test(is_admin)
def admin_dashboard(request):
    """Trang tổng quan - Tối ưu dựa trên model thực tế của Đức"""
    
    # 1. Lấy tất cả đơn đặt phòng để tính toán
    all_bookings = Booking.objects.all()
    
    # 2. Tính toán số liệu cho 3 ô màu trên cùng (Khớp biến HTML)
    # Ô Xanh dương: Tổng đơn đặt
    total_bookings = all_bookings.count()
    # Ô Xanh lá: Đơn đã xác nhận hoặc đã hoàn thành (trả phòng)
    approved_bookings = all_bookings.filter(status__in=['approved', 'completed']).count()
    # Ô Vàng: Đơn đang chờ duyệt
    pending_bookings_count = all_bookings.filter(status='pending').count()
    
    # 3. Danh sách đơn hàng chờ duyệt để hiển thị trong bảng
    pending_bookings = all_bookings.filter(status='pending').select_related('user', 'room').order_by('-created_at')
    
    # 4. Dữ liệu biểu đồ "Trạng thái đơn hàng" (Tiếng Việt hóa từ STATUS_CHOICES)
    status_counts = all_bookings.values('status').annotate(total=Count('id'))
    # Khớp hoàn toàn với STATUS_CHOICES trong model của Đức
    status_map = {
        'pending': 'Chờ duyệt',
        'approved': 'Đã xác nhận',
        'rejected': 'Từ chối',
        'completed': 'Đã trả phòng'
    }
    booking_labels = [status_map.get(item['status'], item['status']) for item in status_counts]
    booking_data = [item['total'] for item in status_counts]
    
    # 5. Dữ liệu biểu đồ "Phân bổ phòng theo khu vực" (Lấy từ field address)
    region_counts = Room.objects.values('address').annotate(total=Count('id'))
    room_labels = [item['address'] for item in region_counts]
    room_data = [item['total'] for item in region_counts]
    
    # 6. Gửi dữ liệu ra màn hình
    context = {
        'total_bookings': total_bookings,
        'approved_bookings': approved_bookings,
        'pending_bookings_count': pending_bookings_count,
        'pending_bookings': pending_bookings,
        'booking_labels': booking_labels,
        'booking_data': booking_data,
        'room_labels': room_labels,
        'room_data': room_data,
        'room_count': Room.objects.count(),
        'user_count': User.objects.count(),
    }
    return render(request, 'core/dashboard.html', context)

@user_passes_test(is_admin)
def manage_booking(request, pk, action):
    """Phê duyệt hoặc từ chối đặt phòng"""
    booking_to_manage = get_object_or_404(Booking, pk=pk)
    
    if action == 'approve':
        booking_to_manage.status = 'approved'
        booking_to_manage.room.is_available = False
        messages.success(request, f"Đã phê duyệt đơn hàng #{booking_to_manage.id}")
    elif action == 'reject':
        booking_to_manage.status = 'rejected'
        booking_to_manage.room.is_available = True
        messages.warning(request, f"Đã từ chối đơn hàng #{booking_to_manage.id}")
        
    booking_to_manage.room.save()
    booking_to_manage.save()
    return redirect('admin_dashboard')

@user_passes_test(is_admin)
def edit_room_image(request, room_id):
    """Chỉnh sửa hình ảnh phòng"""
    room = get_object_or_404(Room, pk=room_id)
    
    if request.method == 'POST':
        form = RoomImageForm(request.POST, request.FILES, instance=room)
        if form.is_valid():
            form.save()
            messages.success(request, f"Cập nhật hình ảnh cho phòng {room.room_number} thành công!")
            return redirect('admin_dashboard')
    else:
        form = RoomImageForm(instance=room)
    
    context = {
        'form': form,
        'room': room,
    }
    return render(request, 'core/edit_room_image.html', context)

@user_passes_test(is_admin)
def manage_rooms(request):
    """Quản lý danh sách phòng (xem, sửa hình ảnh, xóa)"""
    all_rooms = Room.objects.all().order_by('room_number')
    
    context = {
        'rooms': all_rooms,
    }
    return render(request, 'core/manage_rooms.html', context)

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
        admin_username = 'admin_moi'
        admin_password = 'admin12345'
        admin_email = 'admin@hotel.com'

        user, created = User.objects.get_or_create(
            username=admin_username,
            defaults={
                'email': admin_email,
                'is_staff': True,
                'is_superuser': True,
                'is_active': True,
            }
        )

        user.email = admin_email
        user.is_staff = True
        user.is_superuser = True
        user.is_active = True
        user.set_password(admin_password)
        user.save()

        if created:
            return HttpResponse("Khởi tạo Database và Admin thành công! Username: admin_moi, Password: admin12345")
        return HttpResponse("Admin admin_moi đã tồn tại; mật khẩu đã reset về admin12345.")
    except Exception as error:
        return HttpResponse(f"Lỗi khi thiết lập Database: {str(error)}")

@csrf_exempt
def ai_assistant(request):
    """View xử lý Chatbox trực tiếp trên giao diện Website"""
    try:
        incoming_query = ''

        if request.method == 'POST':
            content_type = request.content_type or ''
            if content_type.startswith('application/json'):
                try:
                    payload = json.loads(request.body.decode('utf-8'))
                    incoming_query = payload.get('message', '')
                except Exception:
                    incoming_query = ''
            else:
                incoming_query = request.POST.get('message', '')
        else:
            incoming_query = request.GET.get('message', '')

        incoming_query = incoming_query.strip()
        if not incoming_query:
            return JsonResponse({'reply': "Chào bạn! MyHotel có thể giúp gì cho bạn hôm nay?"})

        return JsonResponse({'reply': get_ai_response(incoming_query)})
    except Exception as exc:
        print(f"AI assistant error: {exc}")
        return JsonResponse({
            'reply': "Xin lỗi, hiện tại hệ thống chat đang gặp sự cố. Vui lòng thử lại sau." 
        }, status=500)

# HẾT FILE VIEWS.PY