""" Task Scheduler

Command called by cron job to list and process (multiprocess) tasks in the background
- Support to multiple model training / applying

Execution in cron:

```
# Task Scheduler every 10 minutes
*/10 * * * * python manage.py task-scheduler
```
"""
import json
import logging
import platform

if platform.system() == 'Windows':
	from threading import Thread as Process
else:
	from multiprocessing import Process

from django.core.management.base import BaseCommand

from texta.settings import ERROR_LOGGER, INFO_LOGGER, MODELS_DIR
from task_manager.models import Task
from task_manager.tasks import task_params

# Define max number of background running processes
MAX_RUNNING = 2


class Command(BaseCommand):

    def handle(self, *args, **options):
        """ Schedule tasks for background execution
        """

        # Get running tasks
        running_tasks = Task.objects.filter(status=Task.STATUS_RUNNING)
        capacity = MAX_RUNNING - len(running_tasks)

        if capacity <= 0:
            # Max running tasks in progress
            log_data = json.dumps({'process': 'Task Scheduler', 'event': 'max_running_tasks'})
            logging.getLogger(INFO_LOGGER).info(log_data)
            return

        # Allocate queued tasks to running tasks
        queued_tasks = Task.objects.filter(status=Task.STATUS_QUEUED)
        queued_tasks = queued_tasks[:capacity]

        for task in queued_tasks:

            task_type = task.task_type
            # TODO: preprocessor should be a task type!
            if task_type in ['train_tagger', 'train_model']:
            	model = activate_model(task_type)
            	model.train(task_id)
            else:
            	Preprocessor().apply(task_id)
