from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'List all admin/superuser accounts.'

    def handle(self, *args, **options):
        User = get_user_model()
        admins = User.objects.filter(is_staff=True)
        
        if not admins.exists():
            self.stdout.write(self.style.WARNING('No admin users found.'))
            return

        self.stdout.write(self.style.SUCCESS(f'Found {admins.count()} admin user(s):'))
        for user in admins:
            status = "Superuser" if user.is_superuser else "Staff"
            self.stdout.write(f'  - {user.username} ({user.email}) [{status}]')
