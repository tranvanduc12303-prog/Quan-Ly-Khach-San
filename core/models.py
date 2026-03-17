from django.db import models
from django.contrib.auth.models import User
from django.core.exceptions import ValidationError
from django.core.validators import MinValueValidator, MaxValueValidator
from cloudinary.models import CloudinaryField

# 1. Bảng Loại phòng
class RoomType(models.Model):
    name = models.CharField("Tên loại phòng", max_length=100)
    description = models.TextField("Mô tả", blank=True)

    class Meta:
        verbose_name_plural = "Loại phòng"

    def __str__(self):
        return self.name

# 2. Bảng Phòng
class Room(models.Model):
    room_number = models.CharField("Số phòng", max_length=10, unique=True)
    room_type = models.ForeignKey(RoomType, on_delete=models.CASCADE, verbose_name="Loại phòng")
    image = CloudinaryField('Ảnh đại diện', folder='rooms/', null=True, blank=True)
    price = models.DecimalField("Giá mỗi đêm", max_digits=12, decimal_places=0)
    is_available = models.BooleanField("Còn trống", default=True)
    address = models.CharField("Địa chỉ/Thành phố", max_length=255, default="Hà Nội") 
    description = models.TextField("Mô tả phòng", blank=True) 

    class Meta:
        verbose_name_plural = "Phòng"

    def __str__(self):
        return f"Phòng {self.room_number} ({self.room_type.name})"

    @property
    def average_rating(self):
        reviews = self.reviews.all()
        if reviews.exists():
            return round(sum(r.rating for r in reviews) / reviews.count(), 1)
        return 0

# 3. Bảng Dịch vụ
class Service(models.Model):
    name = models.CharField("Tên dịch vụ", max_length=100)
    price = models.DecimalField("Giá dịch vụ", max_digits=12, decimal_places=0)

    class Meta:
        verbose_name_plural = "Dịch vụ"

    def __str__(self):
        return self.name

# 4. Bảng Đặt phòng
class Booking(models.Model):
    STATUS_CHOICES = [
        ('pending', 'Chờ duyệt'),
        ('approved', 'Đã xác nhận'),
        ('rejected', 'Từ chối'),
        ('completed', 'Đã trả phòng'),
    ]
    
    PAYMENT_METHODS = [
        ('cod', 'Thanh toán tại quầy'),
        ('momo', 'Ví MoMo'),
        ('vnpay', 'VNPay / Ngân hàng'),
        ('transfer', 'Chuyển khoản trực tiếp'),
    ]

    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Khách hàng")
    room = models.ForeignKey(Room, on_delete=models.CASCADE, verbose_name="Phòng")
    services = models.ManyToManyField(Service, blank=True, verbose_name="Dịch vụ đi kèm")
    check_in = models.DateField("Ngày nhận phòng")
    check_out = models.DateField("Ngày trả phòng")
    status = models.CharField("Trạng thái đơn", max_length=10, choices=STATUS_CHOICES, default='pending')
    
    is_paid = models.BooleanField("Đã thanh toán", default=False)
    payment_method = models.CharField("Phương thức thanh toán", max_length=20, choices=PAYMENT_METHODS, default='cod')
    transaction_id = models.CharField("Mã giao dịch", max_length=100, null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Đơn đặt phòng"

    def __str__(self):
        return f"{self.user.username} - {self.room.room_number} ({self.get_status_display()})"

    @property
    def total_price(self):
        if self.check_out and self.check_in:
            nights = (self.check_out - self.check_in).days
            if nights <= 0: nights = 1
            room_bill = nights * self.room.price
            try:
                service_bill = sum(s.price for s in self.services.all())
            except:
                service_bill = 0
            return room_bill + service_bill
        return 0

    def clean(self):
        if self.check_in and self.check_out and self.check_out <= self.check_in:
            raise ValidationError("Ngày trả phòng phải sau ngày nhận phòng!")

# 5. Bảng Đánh giá (PHẢI CÓ ĐOẠN NÀY)
class Review(models.Model):
    room = models.ForeignKey(Room, on_delete=models.CASCADE, related_name='reviews', verbose_name="Phòng")
    user = models.ForeignKey(User, on_delete=models.CASCADE, verbose_name="Người đánh giá")
    rating = models.IntegerField("Điểm đánh giá", validators=[MinValueValidator(1), MaxValueValidator(5)])
    comment = models.TextField("Nhận xét", blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        verbose_name_plural = "Đánh giá"

    def __str__(self):
        return f"{self.user.username} đánh giá {self.room.room_number} - {self.rating} sao"

# 6. Bảng Địa điểm (Bổ sung nếu dự án của bạn có dùng)
class Destination(models.Model):
    name = models.CharField("Tên địa điểm", max_length=200)
    image = CloudinaryField('Ảnh địa điểm', folder='destinations/', null=True, blank=True)
    description = models.TextField("Mô tả", blank=True)

    class Meta:
        verbose_name_plural = "Địa điểm nổi bật"

    def __str__(self):
        return self.name