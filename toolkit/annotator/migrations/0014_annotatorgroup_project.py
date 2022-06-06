# Generated by Django 2.2.28 on 2022-05-12 10:18

from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ('core', '0020_task_task_type'),
        ('annotator', '0013_annotatorgroup'),
    ]

    operations = [
        migrations.AddField(
            model_name='annotatorgroup',
            name='project',
            field=models.ForeignKey(default=None, null=True, on_delete=django.db.models.deletion.CASCADE, to='core.Project'),
        ),
    ]