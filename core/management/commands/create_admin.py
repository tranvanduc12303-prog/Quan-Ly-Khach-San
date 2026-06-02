from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Create or update a Django admin user for the app.'

    def add_arguments(self, parser):
        parser.add_argument('--username', type=str, help='Admin username', default=None)
        parser.add_argument('--email', type=str, help='Admin email', default=None)
        parser.add_argument('--password', type=str, help='Admin password', default=None)

    def handle(self, *args, **options):
        User = get_user_model()
        username = options['username'] or 'admin'
        email = options['email'] or 'admin@example.com'
        password = options['password'] or 'Admin@123'

        user, created = User.objects.get_or_create(username=username, defaults={
            'email': email,
            'is_staff': True,
            'is_superuser': True,
            'is_active': True,
        })

        if created:
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Admin user "{username}" created successfully.'))
        else:
            updated = False
            if not user.is_staff:
                user.is_staff = True
                updated = True
            if not user.is_superuser:
                user.is_superuser = True
                updated = True
            if not user.is_active:
                user.is_active = True
                updated = True
            if password:
                user.set_password(password)
                updated = True
            if updated:
                user.save()
                self.stdout.write(self.style.SUCCESS(f'Admin user "{username}" updated successfully.'))
            else:
                self.stdout.write(self.style.WARNING(f'Admin user "{username}" already exists and is up to date.'))

        self.stdout.write(self.style.NOTICE('Login with this account at /admin/'))
