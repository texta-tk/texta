# Generated by Django 2.2.24 on 2021-10-18 13:53

from django.db import migrations


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0018_delete_phrase'),
    ]

    operations = [
        migrations.RemoveField(
            model_name='task',
            name='progress',
        ),
    ]
