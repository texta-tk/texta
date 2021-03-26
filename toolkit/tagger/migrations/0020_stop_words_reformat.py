import json
from django.db import migrations, models
from toolkit.helper_functions import load_stop_words

def reformat_stop_words(apps, schema_editor):
    Tagger = apps.get_model("tagger", "Tagger")
    for tagger in Tagger.objects.all():
        reformatted_stop_words = json.dumps(load_stop_words(tagger.stop_words))
        tagger.stop_words = reformatted_stop_words
        tagger.save()

class Migration(migrations.Migration):

    dependencies = [
        ('tagger', '0019_taggergroup_task'),
    ]

    operations = [
        migrations.AlterField(
            model_name='tagger',
            name='stop_words',
            field=models.TextField(default='[]'),
        ),
        migrations.RunPython(reformat_stop_words)
    ]
