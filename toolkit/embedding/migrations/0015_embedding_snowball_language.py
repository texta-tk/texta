# Generated by Django 2.2.17 on 2021-04-01 10:03

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('embedding', '0014_embedding_embedding_type'),
    ]

    operations = [
        migrations.AddField(
            model_name='embedding',
            name='snowball_language',
            field=models.CharField(default=None, max_length=1000, null=True),
        ),
    ]
