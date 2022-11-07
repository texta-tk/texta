import argparse
import io
import os

import django  # For making sure the correct Python environment is used.
from texta_tools.minio_wrapper import MinioWrapper

# Setup Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "toolkit.settings")
django.setup()

if __name__ == '__main__':

    parser = argparse.ArgumentParser(description="CLI wrapper for simple S3 related operations through the Minio client.")
    parser.add_argument("--uri", type=str, required=True, help="URI to access S3.")
    parser.add_argument("--access-key", type=str, required=True, help="Access key for S3.")
    parser.add_argument("--secret-key", type=str, required=True, help="Secret key for S3.")
    parser.add_argument("--bucket", type=str, required=True, help="Which bucket to use inside S3.")

    parser.add_argument("--model-type", help="Type of the model to use.", required=True)
    parser.add_argument("--model-id", help="ID of the model to dump.", required=True)
    parser.add_argument("--target-path", type=str, required=True, help="Path inside S3 where to store the file.")

    args = parser.parse_args()

    # Import Object based on model type
    if args.model_type == "bert_tagger":
        from toolkit.bert_tagger.models import BertTagger as ModelToExport
    elif args.model_type == "tagger":
        from toolkit.tagger.models import Tagger as ModelToExport

    # Download as binary
    print("Downloading model:", args.model_id)
    model_object = ModelToExport.objects.get(id=args.model_id)
    zip_bytes = model_object.export_resources()
    zip_size = len(zip_bytes)
    zip_binary = io.BytesIO(zip_bytes)

    # Upload binary to S3
    print("Uploading model:", args.model_id)
    minio = MinioWrapper(args.uri, args.access_key, args.secret_key, args.bucket)
    minio.upload_binary(args.target_path, zip_binary, zip_size)
