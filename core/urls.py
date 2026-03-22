from django.urls import path
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static
from . import views

urlpatterns = [
    # --- 1. TRANG CHỦ, TÌM KIẾM & CHI TIẾT ---
    # Hiển thị danh sách phòng và thanh tìm kiếm
    path('', views.home, name='home'),
    
    # Xem chi tiết phòng, thực hiện đặt phòng và gửi đánh giá (Reviews)
    path('room/<int:pk>/', views.room_detail, name='room_detail'),
    
    # --- 2. QUẢN LÝ DÀNH CHO KHÁCH HÀNG (MY BOOKINGS & PROFILE) ---
    # Xem danh sách "Chỗ nghỉ của tôi"
    path('my-bookings/', views.my_bookings, name='my_bookings'),
    
    # Trang thông tin cá nhân (Profile) hiển thị thống kê và thông tin Đức/Khách hàng
    path('profile/', views.profile, name='profile'),
    
    # Trang chỉnh sửa thông tin cá nhân (Họ tên, Email)
    path('profile/edit/', views.edit_profile, name='edit_profile'),
    
    # Xử lý hủy đơn đặt phòng khi đang chờ duyệt
    path('cancel-booking/<int:pk>/', views.cancel_booking, name='cancel_booking'),
    
    # Trang hiển thị mã QR thanh toán VietQR cho từng đơn hàng
    path('payment/<int:booking_id>/', views.payment_page, name='payment_page'),
    
    # Xác nhận sau khi khách bấm "Tôi đã chuyển khoản" (Dẫn về danh sách đơn)
    path('payment-confirm/<int:booking_id>/', views.my_bookings, name='payment_confirm'),
    
    # --- 3. QUẢN LÝ DÀNH CHO ADMIN (DASHBOARD) ---
    # Trang thống kê biểu đồ, doanh thu và quản lý tập trung
    path('dashboard/', views.admin_dashboard, name='admin_dashboard'),
    
    # Duyệt (approve) hoặc Từ chối (reject) đơn đặt phòng của khách
    path('manage-booking/<int:pk>/<str:action>/', views.manage_booking, name='manage_booking'),
    
    # --- 4. HỆ THỐNG TÀI KHOẢN (AUTHENTICATION) ---
    # Đăng ký tài khoản mới (Để nút "Đăng ký ngay" ở trang Login hoạt động)
    path('register/', views.register, name='register'),
    
    # Đăng nhập (Template nằm trong registration/ theo cấu trúc thư mục của Đức)
    path('login/', auth_views.LoginView.as_view(template_name='registration/login.html'), name='login'),
    
    # Đăng xuất (Chuyển hướng về trang chủ sau khi thoát)
    path('logout/', auth_views.LogoutView.as_view(next_page='home'), name='logout'),
    
    # --- 5. TRỢ LÝ AI & CÔNG CỤ HỆ THỐNG ---
    # Chatbot hỗ trợ tư vấn phòng sử dụng Gemini API (Đã nâng cấp từ Groq)
    path('ai-assistant/', views.ai_assistant, name='ai_assistant'),
    
    # Lệnh khởi tạo Database, tạo Superuser nhanh khi Deploy lên Render
    path('setup-database/', views.setup_database, name='setup_db'),
]

# --- 6. CẤU HÌNH MEDIA & STATIC (PHỤC VỤ HIỂN THỊ ẢNH) ---
# Đảm bảo hình ảnh phòng khách sạn hiện lên chính xác trên mọi môi trường
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)
else:
    # Cấu hình dự phòng bắt buộc cho môi trường Production (Render) để không mất ảnh
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)