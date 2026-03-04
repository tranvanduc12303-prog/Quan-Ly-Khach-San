import pymysql
from pathlib import Path

# Đánh lừa Django rằng chúng ta đang dùng mysqlclient bản mới nhất
pymysql.version_info = (2, 2, 1, "final", 0)
pymysql.install_as_MySQLdb()

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = 'django-insecure-pp57^v&k7h-9_8r^^j)toornmvak23u)h^4xsy-k-$o97s3wpm'

DEBUG = True

ALLOWED_HOSTS = []

# Application definition
INSTALLED_APPS = [
    'core',
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'hotel_management.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'django.template.context_processors.media', # Thêm để hiển thị ảnh
            ],
        },
    },
]

WSGI_APPLICATION = 'hotel_management.wsgi.application'

# Database - Đã cấu hình cho MySQL
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME': 'hotel_db',
        'USER': 'root',
        'PASSWORD': 'Tranvanduc1230399@', 
        'HOST': '127.0.0.1', 
        'PORT': '3306',
    }
}

# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',},
]

# Internationalization - Chuyển sang tiếng Việt và múi giờ Việt Nam
LANGUAGE_CODE = 'vi' # Chuyển sang tiếng Việt

TIME_ZONE = 'Asia/Ho_Chi_Minh' # Múi giờ Việt Nam để ngày đặt phòng chính xác

USE_I18N = True

USE_TZ = True

# Static files (CSS, JavaScript)
STATIC_URL = 'static/'

# --- CẤU HÌNH QUAN TRỌNG BỔ SUNG ---

# 1. Quản lý Hình ảnh (Media Files) - Để ảnh phòng hiện lên
MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

# 2. Điều hướng sau khi Đăng nhập/Đăng xuất
LOGIN_REDIRECT_URL = 'home'
LOGOUT_REDIRECT_URL = 'home'
LOGIN_URL = 'login'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'