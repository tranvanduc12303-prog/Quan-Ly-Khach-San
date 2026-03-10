from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # --- TRANG CHỦ & CHI TIẾT ---
    path('', views.home, name='home'),
    path('room/<int:pk>/', views.room_detail, name='room_detail'),
    
    # --- QUẢN LÝ DÀNH CHO KHÁCH HÀNG ---
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('cancel-booking/<int:pk>/', views.cancel_booking, name='cancel_booking'),
    
    # --- QUẢN LÝ DÀNH CHO ADMIN ---
    # Trang Dashboard thống kê biểu đồ
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    # Luồng duyệt/từ chối đơn đặt phòng
    path('manage-booking/<int:pk>/<str:action>/', views.manage_booking, name='manage_booking'),
    
    # --- ĐĂNG NHẬP & ĐĂNG XUẤT ---
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    
    # --- TRỢ LÝ AI & HỆ THỐNG ---
    path('ai-assistant/', views.ai_assistant, name='ai_assistant'),
    path('setup-db/', views.setup_database, name='setup_db'),
]