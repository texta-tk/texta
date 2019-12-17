# Generated by Django 2.1.7 on 2019-12-16 11:07

from django.db import migrations, models
import multiselectfield.db.fields


class Migration(migrations.Migration):

    dependencies = [
        ('embedding', '0005_remove_model_location_fields'),
    ]

    operations = [
        migrations.AddField(
            model_name='embedding',
            name='indices',
            field=multiselectfield.db.fields.MultiSelectField(default=None, max_length=200),
        ),
        migrations.AlterField(
            model_name='embedding',
            name='embedding_model',
            field=models.FileField(default=None, null=True, upload_to='', verbose_name=''),
        ),
        migrations.AlterField(
            model_name='embedding',
            name='phraser_model',
            field=models.FileField(default=None, null=True, upload_to='', verbose_name=''),
        ),
        migrations.AlterField(
            model_name='embeddingcluster',
            name='cluster_model',
            field=models.FileField(default=None, null=True, upload_to='', verbose_name=''),
        ),
    ]
