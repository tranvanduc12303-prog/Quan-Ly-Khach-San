from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    # ĐÂY LÀ DÒNG QUAN TRỌNG NHẤT:
    path('', include('core.urls')), 
    path('accounts/', include('django.contrib.auth.urls')),
] 

# Phục vụ file ảnh (Yêu cầu 3e)
if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
    from django.conf import settings
from django.conf.urls.static import static

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)