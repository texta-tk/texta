# Generated by Django 2.2.17 on 2021-01-28 09:39

from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ('embedding', '0013_embedding_use_phraser'),
    ]

    operations = [
        migrations.AddField(
            model_name='embedding',
            name='embedding_type',
            field=models.TextField(default='W2VEmbedding'),
        ),
    ]
