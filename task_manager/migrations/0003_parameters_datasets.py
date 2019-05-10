# Generated by Django 2.0.2 on 2019-01-23 14:21

import uuid
import os
from django.db import migrations, models
from utils.helper_functions import get_wildcard_files, create_file_path
from texta.settings import MODELS_DIR
from texta.settings import PROTECTED_MEDIA
from texta.settings import STATIC_URL, URL_PREFIX, MIGRATION_LOGGER
import json
import logging


def listify_dataset(apps, schema_editor):
    logging.getLogger(MIGRATION_LOGGER).info(json.dumps({'process':'listify_dataset', 'info': 'Transforming task params dataset to datasets.'}))

    Task = apps.get_model('task_manager', 'Task')
    for task in Task.objects.all():
        try:
            params = json.loads(task.parameters)
            if not type(params['dataset']) == list:
                params['dataset'] = [params['dataset']]
            task.parameters = json.dumps(params)
            logging.getLogger(MIGRATION_LOGGER).info(json.dumps({'process':'listify_dataset', 'new_datasets_value': params['dataset'], 'task_id': task.id, 'task_type': task.task_type}))
            task.save()
        except Exception as e:
            logging.getLogger(MIGRATION_LOGGER).info(json.dumps({'process':'rename_files', 'ERROR': 'Exception occurred {}'.format(e), 'task_id': task.id, 'task_type': task.task_type}))
            print('Exception occurred on Task: {}'.format(task.id))
            print(e)


class Migration(migrations.Migration):

    dependencies = [
        ('task_manager', '0002_unique_id'),
    ]

    operations = [
        migrations.RunPython(listify_dataset),
    ]