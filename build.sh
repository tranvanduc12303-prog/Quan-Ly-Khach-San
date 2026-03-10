#!/usr/bin/env bash
# Thoát ngay nếu có lỗi
set -o errexit

# 1. Cài đặt thư viện (Chỉ cần 1 lần)
pip install -r requirements.txt

# 2. Gom các file tĩnh (CSS, JS)
python manage.py collectstatic --no-input

# 3. Cập nhật cấu trúc database (Quan trọng nhất để hết lỗi 500)
python manage.py migrate

# 4. TỰ ĐỘNG TẠO ADMIN (Để bạn có thể đăng nhập ngay)
# Tài khoản: admin_render | Mật khẩu: matkhau123
python manage.py shell -c "from django.contrib.auth.models import User; User.objects.filter(username='admin_render').exists() or User.objects.create_superuser('admin_render', 'admin@example.com', 'matkhau123')"

# 5. Đổ dữ liệu mẫu (Chỉ dùng nếu bạn có file data.json chuẩn)
# Nếu bạn chưa có file này hoặc bị lỗi, hãy thêm dấu # ở đầu dòng dưới
# python manage.py loaddata data.json