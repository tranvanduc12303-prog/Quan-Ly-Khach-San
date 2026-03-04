from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator

# 1. Bảng Loại phòng
class RoomType(models.Model):
    name = models.CharField("Tên loại phòng", max_length=100)
    description = models.TextField("Mô tả", blank=True)

    def __str__(self):
        return self.name

# 2. Bảng Phòng
class Room(models.Model):
    room_number = models.CharField("Số phòng", max_length=10)
    room_type = models.ForeignKey(RoomType, on_delete=models.CASCADE, verbose_name="Loại phòng")
    image = models.ImageField("Ảnh đại diện", upload_to='rooms/', null=True, blank=True)
    price = models.DecimalField("Giá mỗi đêm", max_digits=10, decimal_places=2)
    is_available = models.BooleanField("Còn trống", default=True)
    address = models.CharField("Địa chỉ/Thành phố", max_length=255, default="Hà Nội") 
    description = models.TextField("Mô tả phòng", blank=True) 

    def __str__(self):
        return f"Phòng {self.room_number} ({self.room_type.name})"

    # CẢI TIẾN: Tính điểm trung bình của phòng
    @property
    def average_rating(self):
        reviews = self.reviews.all()
        if reviews.exists():
            total = sum(review.rating for review in reviews)
            return round(total / reviews.count(), 1)
        return 0

    # CẢI TIẾN: Đếm tổng số đánh giá
    @property
    def review_count(self):
        return self.reviews.count()

# 3. Bảng Đặt phòng
class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Chờ duyệt'),
        ('approved', 'Đã xác nhận'),
        ('rejected', 'Từ chối'),
    ]
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Khách hàng")
    room = models.ForeignKey(Room, on_delete=models.CASCADE, verbose_name="Phòng")
    check_in = models.DateField("Ngày nhận phòng")
    check_out = models.DateField("Ngày trả phòng")
    status = models.CharField("Trạng thái", max_length=10, choices=STATUS_CHOICES, default='pending')
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} - {self.room.room_number}"

    @property
    def total_price(self):
        if self.check_out and self.check_in:
            delta = self.check_out - self.check_in
            nights = delta.days
            if nights <= 0: nights = 1
            return nights * self.room.price
        return 0

    def clean(self):
        if self.check_in and self.check_out:
            if self.check_out < self.check_in:
                raise ValidationError("Ngày trả phòng không thể trước ngày nhận phòng!")

# 4. Bảng Dịch vụ
class Service(models.Model):
    name = models.CharField("Tên dịch vụ", max_length=100)
    price = models.DecimalField("Giá dịch vụ", max_digits=10, decimal_places=2)

    def __str__(self):
        return self.name

# 5. Bảng Đánh giá (Đã nâng cấp logic)
class Review(models.Model):
    # Dùng related_name='reviews' để Room dễ dàng truy cập danh sách đánh giá
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='reviews')
    user = models.ForeignKey(User, on_delete=models.CASCADE)
    comment = models.TextField("Bình luận")
    # Thêm validators để giới hạn 1-5 sao
    rating = models.IntegerField(
        "Đánh giá (1-5)", 
        validators=[MinValueValidator(1), MaxValueValidator(5)],
        default=5
    )
    created_at = models.DateTimeField(auto_now_add=True)

    def __str__(self):
        return f"{self.user.username} đánh giá {self.rating} sao cho {self.room.room_number}"

# 6. Bảng Địa điểm thu hút
class Destination(models.Model):
    name = models.CharField("Tên địa điểm", max_length=100)
    image = models.ImageField("Hình ảnh", upload_to='destinations/')
    booking_count = models.IntegerField("Số chỗ ở", default=0)

    def __str__(self):
        return self.name
    