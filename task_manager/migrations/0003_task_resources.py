# Generated by Django 2.0.4 on 2019-02-04 11:07

from django.db import migrations
import picklefield.fields


class Migration(migrations.Migration):

    dependencies = [
        ('task_manager', '0002_unique_id'),
    ]

    operations = [
        migrations.AddField(
            model_name='task',
            name='resources',
            field=picklefield.fields.PickledObjectField(default=None, editable=False, null=True),
        ),
    ]
