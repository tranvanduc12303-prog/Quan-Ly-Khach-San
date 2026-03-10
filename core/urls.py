from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Trang chủ
    path('', views.home, name='home'),
    
    # Chi tiết phòng và Đặt phòng
    path('room/<int:pk>/', views.room_detail, name='room_detail'),
    
    # Danh sách phòng đã đặt (Chỗ nghỉ của tôi)
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    
    # Hủy đơn đặt phòng
    path('cancel-booking/<int:pk>/', views.cancel_booking, name='cancel_booking'),
    
    # Đăng nhập & Đăng xuất
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'), # Thêm next_page để về trang chủ
]
path('setup-db/', views.setup_database),