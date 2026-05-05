import os
import sys
import django
import io

# Fix encoding for Vietnamese characters
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

# Thêm đường dẫn dự án vào sys.path
sys.path.append(r'd:\Quan Ly Khach San')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotel_management.settings')

# Khởi tạo Django
django.setup()

from core.models import Room, RoomType, Service
from core.views import get_room_response

# Test các câu hỏi
test_questions = [
    # Câu hỏi về địa chỉ/vị trí
    "Khách sạn ở đâu?",
    "Vị trí của MyHotel là gì?",
    "Khách sạn tọa lạc ở khu vực nào?",
    
    # Câu hỏi về phòng trống
    "Có phòng trống không?",
    "Phòng nào còn trống?",
    "Hiện tại còn bao nhiêu phòng?",
    
    # Câu hỏi về giá
    "Giá phòng bao nhiêu?",
    "Phòng rẻ nhất bao nhiêu tiền?",
    "Chi phí phòng là bao nhiêu?",
    "Giá trung bình phòng?",
    
    # Câu hỏi về loại phòng
    "Có những loại phòng nào?",
    "Phòng nào khác nhau?",
    "Phòng đôi giá bao nhiêu?",
    "Phòng gia đình có không?",
    "Phòng một người giá bao nhiêu?",
    
    # Câu hỏi về dịch vụ/tiện ích
    "Phòng có những gì?",
    "Dịch vụ gì có?",
    "Có WiFi không?",
    "Phòng tắm như thế nào?",
    "Có máy điều hòa không?",
    
    # Câu hỏi về đặt phòng
    "Cách đặt phòng?",
    "Làm sao đặt phòng?",
    "Quy trình đặt phòng như thế nào?",
    
    # Câu hỏi về hủy phòng
    "Hủy phòng như thế nào?",
    "Có thể hủy đặt phòng không?",
    "Huỷ bỏ đặt phòng được không?",
    
    # Câu hỏi về đánh giá
    "Phòng tốt không?",
    "Có đánh giá nào không?",
    "Khách hàng đánh giá thế nào?",
    "Phòng nào được yêu thích nhất?",
    
    # Câu hỏi về thanh toán
    "Thanh toán như thế nào?",
    "Có chấp nhận thẻ không?",
    "Thanh toán qua ngân hàng được không?",
    
    # Câu hỏi về liên hệ/hỗ trợ
    "Liên hệ MyHotel như thế nào?",
    "Hotline bao nhiêu?",
    "Có hỗ trợ 24/7 không?",
    
    # Câu hỏi khác
    "Xin chào",
    "Bạn là ai?",
    "Tôi muốn biết thêm về MyHotel",
    "Giảm giá có không?",
    "Khách sạn ở gần sân bay không?",
]

print("Testing get_room_response function:")
print("=" * 50)

for question in test_questions:
    response = get_room_response(question)
    print(f"Q: {question}")
    print(f"A: {response}")
    print("-" * 50)