from django.contrib import admin
from .models import RoomType, Room, Booking, Service, Review, Destination

# Admin class for Room (with image handling)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'room_type', 'price', 'is_available', 'address')
    list_filter = ('room_type', 'is_available', 'address')
    search_fields = ('room_number', 'address')
    fields = ('room_number', 'room_type', 'price', 'is_available', 'address', 'description', 'image')

# Admin class for Destination (with image handling)
class DestinationAdmin(admin.ModelAdmin):
    list_display = ('name', 'description')
    fields = ('name', 'description', 'image')

# Đăng ký các model để chúng hiện ra trong trang quản trị
admin.site.register(RoomType)
admin.site.register(Room, RoomAdmin)
admin.site.register(Booking)
admin.site.register(Service)
admin.site.register(Review)
admin.site.register(Destination, DestinationAdmin)
