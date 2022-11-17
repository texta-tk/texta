from cryptography.fernet import Fernet

from django.core.management.base import BaseCommand


class Command(BaseCommand):
    help = 'Generate the 128-bit AES keys.'

    def handle(self, *args, **options):
        key = Fernet.generate_key()
        message = key.decode("utf8").strip()
        print(message)
