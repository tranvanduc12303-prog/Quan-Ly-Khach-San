from django import forms
from django.contrib import admin
from django.utils.html import format_html
from .models import RoomType, Room, Booking, Service, Review, Destination

class DestinationAdminForm(forms.ModelForm):
    class Meta:
        model = Destination
        fields = '__all__'
        widgets = {
            'image': forms.ClearableFileInput(attrs={'class': 'vClearableFileInput'}),
        }

# Admin class for Room (with image handling)
class RoomAdmin(admin.ModelAdmin):
    list_display = ('room_number', 'room_type', 'price', 'is_available', 'address')
    list_filter = ('room_type', 'is_available', 'address')
    search_fields = ('room_number', 'address')
    fields = ('room_number', 'room_type', 'image', 'price', 'is_available', 'address', 'description')

# Admin class for Destination (with image handling)
class DestinationAdmin(admin.ModelAdmin):
    form = DestinationAdminForm
    list_display = ('name',)
    fields = ('name', 'description', 'image', 'image_preview')
    readonly_fields = ('image_preview',)

    def image_preview(self, obj):
        if obj.image:
            return format_html('<img src="{}" style="max-height: 150px; max-width: 250px;" />', obj.image.url)
        return "Chưa có ảnh"
    image_preview.short_description = 'Ảnh hiện tại'

# Đăng ký các model để chúng hiện ra trong trang quản trị
admin.site.register(RoomType)
admin.site.register(Room, RoomAdmin)
admin.site.register(Booking)
admin.site.register(Service)
admin.site.register(Review)
admin.site.register(Destination, DestinationAdmin)
