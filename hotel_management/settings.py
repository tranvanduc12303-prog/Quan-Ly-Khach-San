import os
from pathlib import Path
import dj_database_url
from urllib.parse import quote_plus
import cloudinary
import cloudinary.uploader
import cloudinary.api

# --- ĐƯỜNG DẪN CƠ SỞ ---
BASE_DIR = Path(__file__).resolve().parent.parent

# --- BẢO MẬT & DEBUG ---
SECRET_KEY = os.environ.get('SECRET_KEY', 'django-insecure-full-clean-key-2026')

# DEBUG mặc định từ môi trường hoặc False nếu không có biến môi trường
DEBUG = True

_allowed_hosts_env = os.environ.get('ALLOWED_HOSTS')
if _allowed_hosts_env:
    ALLOWED_HOSTS = [host.strip() for host in _allowed_hosts_env.split(',') if host.strip()]
else:
    ALLOWED_HOSTS = ['localhost', '127.0.0.1', '0.0.0.0', '.onrender.com']

# --- GOOGLE GEMINI API KEY ---
# Chỉ lấy key từ biến môi trường, không dùng fallback cứng.
GEMINI_API_KEY = os.environ.get('GEMINI_API_KEY')

# --- DANH SÁCH ỨNG DỤNG ---
INSTALLED_APPS = [
    'cloudinary_storage',         # Phải nằm trên cùng
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'whitenoise.runserver_nostatic',
    'django.contrib.staticfiles',
    'cloudinary',                 # Thư viện Cloudinary
    'core',                       # App của bạn
]

# --- CÁC LỚP TRUNG GIAN (MIDDLEWARE) ---
MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', # Phải nằm sau SecurityMiddleware
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
_env_database_url = os.environ.get('DATABASE_URL', '').strip()
_env_internal_database = os.environ.get('INTERNAL_DATABASE', '').strip()
_env_external_database = os.environ.get('EXTERNAL_DATABASE', '').strip()
_env_internal_database_url = os.environ.get('INTERNAL_DATABASE_URL', '').strip()
_env_external_database_url = os.environ.get('EXTERNAL_DATABASE_URL', '').strip()

_db_user = os.environ.get('DATABASE_USER') or os.environ.get('USER', '')
_db_pass = os.environ.get('DATABASE_PASS') or os.environ.get('PASS', '')
_db_name = os.environ.get('DATABASE_NAME') or os.environ.get('NAME', '')
_db_host = os.environ.get('DATABASE_HOST') or os.environ.get('HOST', '')
_db_port = os.environ.get('DATABASE_PORT') or os.environ.get('PORT', '5432')

_db_url = (
    _env_database_url
    or _env_internal_database_url
    or _env_external_database_url
    or _env_internal_database
    or _env_external_database
)


def _build_db_url_from_parts():
    if not (_db_user and _db_pass and _db_name and _db_host):
        return None
    return f"postgresql://{_db_user}:{quote_plus(_db_pass)}@{_db_host}:{_db_port}/{_db_name}"


def _is_valid_db_url(value):
    return bool(value and '://' in value and '@' in value)

if _is_valid_db_url(_db_url):
    DATABASES = {
        'default': dj_database_url.config(default=_db_url, conn_max_age=600)
    }
elif built := _build_db_url_from_parts():
    DATABASES = {
        'default': dj_database_url.config(default=built, conn_max_age=600)
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }

# --- TẬP TIN TĨNH (STATIC FILES) ---
STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / "staticfiles"
STATICFILES_DIRS = [BASE_DIR / "static"]
STATICFILES_STORAGE = 'whitenoise.storage.CompressedManifestStaticFilesStorage'

# --- CẤU HÌNH CLOUDINARY (MEDIA FILES) ---
CLOUDINARY_URL = os.environ.get('CLOUDINARY_URL')
CLOUDINARY_STORAGE = {
    'CLOUD_NAME': os.environ.get('CLOUDINARY_CLOUD_NAME', ''),
    'API_KEY': os.environ.get('CLOUDINARY_API_KEY', ''),
    'API_SECRET': os.environ.get('CLOUDINARY_API_SECRET', os.environ.get('CLOUDINARY_APT_SECRET', '')),
}

# Cấu hình Cloudinary SDK nếu người dùng đã cấu hình biến môi trường
if CLOUDINARY_URL:
    cloudinary.config(cloudinary_url=CLOUDINARY_URL, secure=True)
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
elif CLOUDINARY_STORAGE['CLOUD_NAME'] and CLOUDINARY_STORAGE['API_KEY'] and CLOUDINARY_STORAGE['API_SECRET']:
    cloudinary.config(
        cloud_name=CLOUDINARY_STORAGE['CLOUD_NAME'],
        api_key=CLOUDINARY_STORAGE['API_KEY'],
        api_secret=CLOUDINARY_STORAGE['API_SECRET'],
        secure=True
    )
    DEFAULT_FILE_STORAGE = 'cloudinary_storage.storage.MediaCloudinaryStorage'
else:
    DEFAULT_FILE_STORAGE = 'django.core.files.storage.FileSystemStorage'

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