import pathlib

from django.db import migrations

from toolkit.settings import RELATIVE_MODELS_PATH


def transfer_existing_embedding_paths(apps, schema_editor):
    """
    Function for translating full paths to model files to relative ones.
    """
    embedding_models = apps.get_model("embedding", "Embedding")
    for embedding in embedding_models.objects.all():
        if embedding.embedding_model:
            # Take only the file name without the source paths.
            file_name = pathlib.Path(embedding.embedding_model.name).name
            new_path = pathlib.Path(RELATIVE_MODELS_PATH) / "embedding" / file_name
            embedding.embedding_model.name = str(new_path)

        if embedding.phraser_model:
            file_name = pathlib.Path(embedding.phraser_model.name).name
            new_path = pathlib.Path(RELATIVE_MODELS_PATH) / "embedding" / file_name
            embedding.phraser_model.name = str(new_path)

        embedding.save()


class Migration(migrations.Migration):
    dependencies = [
        ('embedding', '0010_auto_20200312_1804'),
    ]

    operations = [
        migrations.RunPython(transfer_existing_embedding_paths)
    ]
