import os
import sys
import django

# Thêm đường dẫn dự án vào sys.path
sys.path.append('d:\Quan Ly Khach San')
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'hotel_management.settings')

# Khởi tạo Django
django.setup()

from core.models import Room, RoomType, Service
from core.views import get_room_response

# Test các câu hỏi
test_questions = [
    "Có phòng trống không?",
    "Giá phòng bao nhiêu?",
    "Khách sạn ở đâu?",
    "Có những loại phòng nào?",
    "Bao nhiêu phòng?",
    "Dịch vụ gì có?",
    "Đánh giá thế nào?",
    "Xin chào",
    "Tôi muốn đặt phòng",
    "Làm sao hủy phòng?"
]

print("Testing get_room_response function:")
print("=" * 50)

for question in test_questions:
    response = get_room_response(question)
    print(f"Q: {question}")
    print(f"A: {response}")
    print("-" * 50)