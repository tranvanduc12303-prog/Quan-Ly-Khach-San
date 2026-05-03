from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # Kết nối toàn bộ chức năng của app core
    path('', include('core.urls')), 
    # Hệ thống đăng nhập/đăng xuất mặc định của Django
    path('accounts/', include('django.contrib.auth.urls')),
] 

# --- CẤU HÌNH HIỂN THỊ HÌNH ẢNH (QUAN TRỌNG) ---
# Cho phép hiển thị ảnh Media và Static ngay cả khi DEBUG = False trên Render
urlpatterns += static(settings.STATIC_URL, document_root=settings.STATIC_ROOT)

# Phục vụ Media khi dùng Storage nội bộ (cả DEBUG True và False nếu MEDIA_URL là đường dẫn nội bộ)
if settings.MEDIA_URL.startswith('/'):
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)