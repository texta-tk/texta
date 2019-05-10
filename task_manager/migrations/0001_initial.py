# Generated by Django 2.1.7 on 2019-04-29 09:41

from django.conf import settings
from django.db import migrations, models
import django.db.models.deletion
import uuid


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name='TagFeedback',
            fields=[
                ('id', models.AutoField(auto_created=True, primary_key=True, serialize=False, verbose_name='ID')),
                ('document', models.TextField()),
                ('prediction', models.IntegerField(default=None)),
                ('in_dataset', models.IntegerField(default=0)),
                ('time_updated', models.DateTimeField(blank=True, default=None, null=True)),
            ],
        ),
        migrations.CreateModel(
            name='Task',
            fields=[
                ('id', models.AutoField(primary_key=True, serialize=False)),
                ('unique_id', models.UUIDField(default=uuid.uuid4, editable=False, unique=True)),
                ('description', models.CharField(default=None, max_length=100)),
                ('task_type', models.CharField(default=None, max_length=100)),
                ('parameters', models.TextField(default=None)),
                ('result', models.TextField(default=None)),
                ('status', models.CharField(choices=[('created', 'Created'), ('queued', 'Queued'), ('running', 'Running'), ('updating', 'Updating'), ('completed', 'Completed'), ('canceled', 'Canceled'), ('failed', 'Failed')], max_length=100)),
                ('progress', models.FloatField(default=0.0)),
                ('progress_message', models.CharField(default='', max_length=100)),
                ('time_started', models.DateTimeField()),
                ('last_update', models.DateTimeField(blank=True, default=None, null=True)),
                ('time_completed', models.DateTimeField(blank=True, default=None, null=True)),
                ('user', models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL)),
            ],
        ),
        migrations.AddField(
            model_name='tagfeedback',
            name='tagger',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to='task_manager.Task'),
        ),
        migrations.AddField(
            model_name='tagfeedback',
            name='user',
            field=models.ForeignKey(on_delete=django.db.models.deletion.CASCADE, to=settings.AUTH_USER_MODEL),
        ),
    ]