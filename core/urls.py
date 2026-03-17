from django.urls import path
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    # --- 1. TRANG CHỦ & CHI TIẾT ---
    # Hiển thị danh sách phòng và tìm kiếm
    path('', views.home, name='home'),
    # Xem chi tiết phòng, đặt phòng và gửi đánh giá
    path('room/<int:pk>/', views.room_detail, name='room_detail'),
    
    # --- 2. QUẢN LÝ DÀNH CHO KHÁCH HÀNG ---
    # Xem lịch sử đơn hàng của cá nhân
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    # Trang hiển thị mã QR thanh toán VietQR (Khắc phục lỗi 500)
    path('payment/<int:booking_id>/', views.payment_page, name='payment_page'),
    
    # --- 3. QUẢN LÝ DÀNH CHO ADMIN ---
    # Trang thống kê biểu đồ Tiếng Việt
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    # Duyệt (approve) hoặc Từ chối (reject) đơn đặt phòng
    path('manage-booking/<int:pk>/<str:action>/', views.manage_booking, name='manage_booking'),
    
    # --- 4. HỆ THỐNG TÀI KHOẢN (AUTH) ---
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    
    # --- 5. TRỢ LÝ AI & HỆ THỐNG ---
    # Chatbot tư vấn phòng trống
    path('ai-assistant/', views.ai_assistant, name='ai_assistant'),
    # Lệnh khởi tạo database nhanh trên Render
    path('setup-database/', views.setup_database, name='setup_db'),
]

# --- 6. CẤU HÌNH HÌNH ẢNH & CSS ---
# Cấu hình này giúp ảnh phòng hiện lên chính xác trên môi trường Deploy
urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)