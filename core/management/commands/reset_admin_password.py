from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Reset password for an existing admin user.'

    def add_arguments(self, parser):
        parser.add_argument('username', type=str, help='Admin username')
        parser.add_argument('--password', type=str, help='New password', default=None)

    def handle(self, *args, **options):
        User = get_user_model()
        username = options['username']
        password = options['password'] or 'Admin@123'

        try:
            user = User.objects.get(username=username)
            user.set_password(password)
            user.save()
            self.stdout.write(self.style.SUCCESS(f'Password for user "{username}" reset successfully.'))
            self.stdout.write(self.style.NOTICE(f'New password: {password}'))
        except User.DoesNotExist:
            self.stdout.write(self.style.ERROR(f'User "{username}" not found.'))
