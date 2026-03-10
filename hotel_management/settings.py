import os
from pathlib import Path
import dj_database_url

# --- ĐƯỜNG DẪN CƠ SỞ ---
BASE_DIR = Path(__file__).resolve().parent.parent

# --- BẢO MẬT & DEBUG ---
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-full-clean-key-2026')

# Tự động tắt Debug khi lên Render để bảo mật
DEBUG = os.environ.get('DEBUG', 'False') == 'True'

# Cho phép chạy trên mọi tên miền (quan trọng cho Render)
ALLOWED_HOSTS = ['*']

# --- DANH SÁCH ỨNG DỤNG ---
INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'core',
]

# --- CÁC LỚP TRUNG GIAN (MIDDLEWARE) ---
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Hiển thị CSS trên Render
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

# --- CƠ SỞ DỮ LIỆU (FIX CỨNG ĐỂ KHÔNG MẤT DỮ LIỆU) ---
# Nếu có biến môi trường DATABASE_URL (Trên Render), dùng Postgres. 
# Nếu không (Dưới máy), dùng SQLite để đơn giản.
DATABASES = {
    'default': dj_database_url.config(
        default=f'sqlite:///{BASE_DIR / "db.sqlite3"}',
        conn_max_age=600
    )
}

# --- KIỂM TRA MẬT KHẨU ---
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# --- ĐA NGÔN NGỮ & THỜI GIAN ---
LANGUAGE_CODE = 'vi'
TIME_ZONE = 'Asia/Ho_Chi_Minh'
USE_I18N = True
USE_TZ = True

# --- TẬP TIN TĨNH (STATIC FILES) ---
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]

# Tối ưu hóa file tĩnh cho Render (WhiteNoise)
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# --- TẬP TIN MEDIA ---
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# --- ĐIỀU HƯỚNG ---
LOGIN_URL = 'login'
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'