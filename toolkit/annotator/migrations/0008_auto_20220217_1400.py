# Generated by Django 2.2.26 on 2022-02-17 12:00

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('annotator', '0007_annotator_add_facts_mapping'),
    ]

    operations = [
        migrations.AlterField(
            model_name='annotator',
            name='add_facts_mapping',
            field=models.BooleanField(default=True),
        ),
    ]