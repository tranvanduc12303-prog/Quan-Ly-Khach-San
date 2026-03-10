import os
from pathlib import Path
import dj_database_url

# --- ĐƯỜNG DẪN CƠ SỞ ---
BASE_DIR = Path(__file__).resolve().parent.parent

# --- BẢO MẬT & DEBUG ---
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-full-clean-key-2026')

# ÉP BUỘC DEBUG = False KHI LÊN PRODUCTION (RENDER)
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

ALLOWED_HOSTS = ['*'] 

# --- DANH SÁCH ỨNG DỤNG ---
INSTALLED_APPS = [
    # Phải đặt cloudinary_storage TRƯỚC staticfiles
    'cloudinary_storage',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    
    # Cloudinary app
    'cloudinary',
    
    # App của bạn
    'core',
]

# --- CÁC LỚP TRUNG GIAN (MIDDLEWARE) ---
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'hotel_management.urls'

# --- GIAO DIỆN (TEMPLATES) ---
TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'hotel_management.wsgi.application'

# --- CƠ SỞ DỮ LIỆU ---
DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600
    )
}

# --- TẬP TIN TĨNH (WHITE NOISE) ---
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# --- CẤU HÌNH CLOUDINARY (LƯU TRỮ ẢNH VĨNH VIỄN) ---
# Thay thế các thông tin dưới đây bằng thông tin từ Dashboard Cloudinary của bạn
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': 'your_cloud_name', 
    'API_KEY': 'your_api_key',
    'API_SECRET': 'your_api_secret'
}

# Ép buộc Django sử dụng Cloudinary để lưu các tệp upload (Media)
DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'

# Vẫn giữ khai báo Media để dự phòng Local
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# --- ĐIỀU HƯỚNG ---
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

# --- BẢO MẬT KHI DEBUG = FALSE ---
if not DEBUG:
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_SSL_REDIRECT = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'