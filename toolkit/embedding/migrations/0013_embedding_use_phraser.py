# Generated by Django 2.2.17 on 2020-11-30 08:08

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('embedding', '0012_remove_embedding_phraser_model'),
    ]

    operations = [
        migrations.AddField(
            model_name='embedding',
            name='use_phraser',
            field=models.BooleanField(default=True),
        ),
    ]