from cryptography.fernet import Fernet

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Generate the 128-bit AES keys.'

    def handle(self, *args, **options):
        key = Fernet.generate_key()
        self.stdout.write(self.style.SUCCESS(key.decode("utf8")))
