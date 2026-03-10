#!/usr/bin/env bash
# Thoát ngay nếu có lỗi
set -o errexit

# Cài đặt các thư viện từ requirements.txt
pip install -r requirements.txt

# Gom các file giao diện (css, js, images)
python manage.py collectstatic --no-input

# Cập nhật cấu trúc database trên Render
python manage.py migrate

# TỰ ĐỘNG TẠO ADMIN (Thay đổi thông tin bên dưới theo ý bạn)
# User: admin_render | Pass: matkhau123
python manage.py shell -c "from django.contrib.auth.models import User; User.objects.filter(username='admin_render').exists() or User.objects.create_superuser('admin_render', 'admin@example.com', 'matkhau123')"