# Generated by Django 2.2.28 on 2022-05-20 12:12

from django.db import migrations, models
import json


def convert_num_examples_to_classes(apps, schema_editor):
    TorchTagger = apps.get_model("torchtagger", "TorchTagger")
    for tagger in TorchTagger.objects.all():
        classes = list(json.loads(tagger.num_examples).keys())
        tagger.classes = json.dumps(classes, ensure_ascii=False)
        tagger.save()

class Migration(migrations.Migration):

    dependencies = [
        ('torchtagger', '0009_demand_embedding'),
    ]

    operations = [
        migrations.AddField(
            model_name='torchtagger',
            name='classes',
            field=models.TextField(default='[]'),
        ),
        migrations.RunPython(convert_num_examples_to_classes)
    ]
