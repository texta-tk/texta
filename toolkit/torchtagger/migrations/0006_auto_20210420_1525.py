# Generated by Django 2.2.19 on 2021-04-20 12:25

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('torchtagger', '0005_torchtagger_confusion_matrix'),
    ]

    operations = [
        migrations.AddField(
            model_name='torchtagger',
            name='balance',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='torchtagger',
            name='balance_to_max_limit',
            field=models.BooleanField(default=False),
        ),
        migrations.AddField(
            model_name='torchtagger',
            name='use_sentence_shuffle',
            field=models.BooleanField(default=False),
        ),
    ]
