from django.contrib import admin
from .models import RoomType, Room, Booking, Service, Review

# Đăng ký các model để chúng hiện ra trong trang quản trị
admin.site.register(RoomType)
admin.site.register(Room)
admin.site.register(Booking)
admin.site.register(Service)
admin.site.register(Review)
from .models import Destination
admin.site.register(Destination)