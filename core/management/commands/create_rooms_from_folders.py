import mimetypes
import os
from django.core.files.uploadedfile import SimpleUploadedFile
from django.core.management.base import BaseCommand
from core.models import Room, RoomType


class Command(BaseCommand):
    help = 'Create rooms from 4 location folders'

    def add_arguments(self, parser):
        parser.add_argument(
            'base_path',
            type=str,
            help='Root path containing 4 folders: Quảng Ninh, Thái Nguyên, Hồ Chí Minh, Hải Phòng'
        )

    def handle(self, *args, **options):
        base_path = options['base_path']

        if not os.path.isdir(base_path):
                self.stderr.write(self.style.ERROR(f'Path does not exist: {base_path}'))
                return
        folder_names = [
            'Quảng Ninh',
            'Thái Nguyên',
            'Hồ Chí Minh',
            'Hải Phòng',
        ]

        room_mapping = {
            'Quảng Ninh': {'room_number': 'QN01', 'price': 900000, 'description': 'Phòng đẹp gần biển Quảng Ninh, phù hợp du lịch và công tác.'},
            'Thái Nguyên': {'room_number': 'TN01', 'price': 650000, 'description': 'Phòng tiện nghi tại Thái Nguyên, yên tĩnh và rộng rãi.'},
            'Hồ Chí Minh': {'room_number': 'HCM01', 'price': 1200000, 'description': 'Phòng sang trọng tại trung tâm TP. Hồ Chí Minh.'},
            'Hải Phòng': {'room_number': 'HP01', 'price': 850000, 'description': 'Phòng thoáng mát tại Hải Phòng, gần cảng và khu du lịch.'},
        }

        room_type, _ = RoomType.objects.get_or_create(name='Standard', defaults={'description': 'Loại phòng tiêu chuẩn cho các tour du lịch và công tác.'})

        for folder_name in folder_names:
            folder_path = os.path.join(base_path, folder_name)
            if not os.path.isdir(folder_path):
                self.stdout.write(self.style.WARNING(f'Skipping: folder not found {folder_name}'))
                continue

            image_files = [
                f for f in os.listdir(folder_path)
                if f.lower().endswith(('.jpg', '.jpeg', '.png', '.webp'))
            ]
            if not image_files:
                self.stdout.write(self.style.WARNING(f'Skipping {folder_name}: no valid image files found.'))
                continue

            image_files.sort()
            image_path = os.path.join(folder_path, image_files[0])
            mapping = room_mapping.get(folder_name, {})
            room_number = mapping.get('room_number', folder_name[:3].upper())
            price = mapping.get('price', 700000)
            description = mapping.get('description', f'Phòng tại {folder_name} với view đẹp và tiện nghi đầy đủ.')
            address = folder_name

            if Room.objects.filter(room_number=room_number).exists():
                self.stdout.write(self.style.NOTICE(f'Room {room_number} already exists, skipping.'))
                continue

            room = Room(
                room_number=room_number,
                room_type=room_type,
                price=price,
                is_available=True,
                address=address,
                description=description,
            )

            try:
                with open(image_path, 'rb') as f:
                    file_data = f.read()
                content_type = mimetypes.guess_type(image_path)[0] or 'application/octet-stream'
                room.image = SimpleUploadedFile(os.path.basename(image_path).encode('utf-8').decode('utf-8'), file_data, content_type=content_type)
                room.save()
                self.stdout.write(self.style.SUCCESS(f'Room {room_number} created successfully.'))
            except Exception as exc:
                self.stderr.write(self.style.ERROR(f'Failed to create room {room_number}: {exc}'))
