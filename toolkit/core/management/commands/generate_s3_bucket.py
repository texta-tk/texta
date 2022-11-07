from django.core.management.base import BaseCommand
import minio

from toolkit.helper_functions import get_minio_client


class Command(BaseCommand):
    help = 'Helper command to create a S3 bucket.'

    def add_arguments(self, parser):
        parser.add_argument('bucket_name', type=str)

    def handle(self, *args, **options):
        from toolkit.tagger.models import Tagger
        wrapper = get_minio_client()
        try:
            response = wrapper.make_bucket(options["bucket_name"])
            self.stdout.write(self.style.SUCCESS("Successfully added bucket into MINIO"))
        except minio.error.S3Error as e:
            if e.code == "BucketAlreadyOwnedByYou":
                self.stdout.write(self.style.SUCCESS("Bucket already exists, skipping!"))
            else:
                raise e
