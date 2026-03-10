from django.urls import path
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    # --- 1. TRANG CHỦ & CHI TIẾT ---
    path('', views.home, name='home'),
    path('room/<int:pk>/', views.room_detail, name='room_detail'),
    
    # --- 2. QUẢN LÝ DÀNH CHO KHÁCH HÀNG ---
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    path('cancel-booking/<int:pk>/', views.cancel_booking, name='cancel_booking'),
    
    # --- 3. QUẢN LÝ DÀNH CHO ADMIN ---
    # Trang Dashboard thống kê biểu đồ
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    # Luồng duyệt/từ chối đơn đặt phòng (approve/reject)
    path('manage-booking/<int:pk>/<str:action>/', views.manage_booking, name='manage_booking'),
    
    # --- 4. HỆ THỐNG TÀI KHOẢN (AUTH) ---
    path('login/', auth_views.LoginView.as_view(template_name='core/login.html'), name='login'),
    # LogoutView thường mặc định chuyển hướng về LOGOUT_REDIRECT_URL trong settings.py
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    
    # Lưu ý: Bạn nên viết thêm hàm register trong views nếu muốn khách tự đăng ký
    # path('register/', views.register, name='register'), 

    # --- 5. TRỢ LÝ AI & HỆ THỐNG ---
    # Đường dẫn xử lý AJAX cho Chatbot Gemini
    path('ai-assistant/', views.ai_assistant, name='ai_assistant'),
    # Đường dẫn khởi tạo database nhanh
    path('setup-db/', views.setup_database, name='setup_db'),
]

# --- 6. CẤU HÌNH ĐỂ HIỂN THỊ HÌNH ẢNH (MEDIA) ---
# Dòng này cực kỳ quan trọng để ảnh phòng khách sạn hiện ra trên web
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)