# Generated by Django 2.2.28 on 2022-08-08 13:53

import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


def transfer_mlp_worker_tasks(apps, schema_editor):
    # We can't import the Person model directly as it may be a newer
    # version than this migration expects. We use the historical version.
    MLPWorker = apps.get_model('mlp', 'MLPWorker')
    for mlp in MLPWorker.objects.all():
        mlp.tasks.add(mlp.task)


def transfer_lang_worker_tasks(apps, schema_editor):
    # We can't import the Person model directly as it may be a newer
    # version than this migration expects. We use the historical version.
    ApplyLangWorker = apps.get_model('mlp', 'ApplyLangWorker')
    for lang_worker in ApplyLangWorker.objects.all():
        lang_worker.tasks.add(lang_worker.task)


class Migration(migrations.Migration):
    dependencies = [
        ('core', '0022_make_last_update_automatic'),
        ('mlp', '0006_auto_20210611_1240'),
    ]

    operations = [
        migrations.AddField(
            model_name='applylangworker',
            name='tasks',
            field=models.ManyToManyField(to='core.Task'),
        ),
        migrations.AddField(
            model_name='mlpworker',
            name='tasks',
            field=models.ManyToManyField(to='core.Task'),
        ),

        migrations.RunPython(transfer_lang_worker_tasks),
        migrations.RunPython(transfer_mlp_worker_tasks),

        migrations.RemoveField(
            model_name='applylangworker',
            name='task',
        ),
        migrations.RemoveField(
            model_name='mlpworker',
            name='task',
        ),

        migrations.AlterField(
            model_name='applylangworker',
            name='author',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='applylangworker',
            name='description',
            field=models.CharField(help_text='Description of the task to distinguish it from others.', max_length=100),
        ),
        migrations.AlterField(
            model_name='mlpworker',
            name='author',
            field=models.ForeignKey(null=True, on_delete=django.db.models.deletion.SET_NULL, to=settings.AUTH_USER_MODEL),
        ),
        migrations.AlterField(
            model_name='mlpworker',
            name='description',
            field=models.CharField(help_text='Description of the task to distinguish it from others.', max_length=100),
        ),
    ]
