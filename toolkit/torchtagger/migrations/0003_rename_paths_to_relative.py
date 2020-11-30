import pathlib

from django.db import migrations

from toolkit.settings import RELATIVE_MODELS_PATH


def transfer_existing_tagger_paths(apps, schema_editor):
    """
    Function for translating full paths to model files to relative ones.
    """
    TorchTagger = apps.get_model("torchtagger", "TorchTagger")
    for tagger in TorchTagger.objects.all():
        if tagger.model:
            # Take only the file name without the source paths.
            file_name = pathlib.Path(tagger.model.name).name
            new_path = pathlib.Path(RELATIVE_MODELS_PATH) / "torchtagger" / file_name
            tagger.model.name = str(new_path)

        if tagger.text_field:
            file_name = pathlib.Path(tagger.text_field.name).name
            new_path = pathlib.Path(RELATIVE_MODELS_PATH) / "torchtagger" / file_name
            tagger.text_field.name = str(new_path)

        tagger.save()


class Migration(migrations.Migration):
    dependencies = [
        ('torchtagger', '0002_torchtagger_indices'),
    ]

    operations = [
        migrations.RunPython(transfer_existing_tagger_paths)
    ]
