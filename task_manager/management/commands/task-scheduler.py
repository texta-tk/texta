""" Task Scheduler

Command called by cron job to list and process (multiprocess) tasks in the background
- Support to multiple model training / applying

Execution in cron:

```
# Task Scheduler every 1 minute
*/1 * * * * python manage.py task-scheduler
```
"""

import json
import logging

from django.core.management.base import BaseCommand

from texta.settings import ERROR_LOGGER, INFO_LOGGER
from task_manager.models import Task
from task_manager.tasks.task_params import activate_task_worker

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
        queued_tasks = Task.objects.filter(status=Task.STATUS_QUEUED).order_by('last_update')
        print("------------------------------------------------------")
        print("-> Total of queued tasks: ", len(queued_tasks))
        print("-> Current capacity: ", capacity)
        print("------------------------------------------------------")
        # Execute one task from queue
        task = queued_tasks[0]
        task_type = task.task_type
        task_id = task.id
        worker = activate_task_worker(task_type)

        if worker is None:
            # Invalid task
            task.update_status(Task.STATUS_FAILED)
            log_data = json.dumps({'process': 'Task Scheduler', 'event': 'invalid_task'})
            logging.getLogger(ERROR_LOGGER).info(log_data)
            return

        try:
            # Run worker
            worker.run(task_id)
        except Exception as e:
            # Capture generic task error
            print(e)
            task.update_status(Task.STATUS_FAILED)
            log_data = json.dumps({'process': 'Task Scheduler', 'event': 'task_execution_error'})
            logging.getLogger(ERROR_LOGGER).info(log_data)
