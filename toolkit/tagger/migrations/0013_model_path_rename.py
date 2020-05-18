import pathlib

from django.db import migrations

from toolkit.settings import RELATIVE_MODELS_PATH


def transfer_existing_tagger_model_path(apps, schema_editor):
    """
    Function for translating full paths to model files to relative ones.
    """
    tagger_models = apps.get_model("tagger", "Tagger")
    for tagger in tagger_models.objects.all():
        if tagger.model:
            # Take only the file name without the source paths.
            file_name = pathlib.Path(tagger.model.name).name
            new_path = pathlib.Path(RELATIVE_MODELS_PATH) / "tagger" / file_name
            tagger.model.name = str(new_path)
            tagger.save()


class Migration(migrations.Migration):
    dependencies = [
        ('tagger', '0012_auto_20200309_1630'),
    ]

    operations = [
        migrations.RunPython(transfer_existing_tagger_model_path)
    ]
