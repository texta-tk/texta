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

from datetime import datetime
from dateutil.relativedelta import relativedelta

from django.core.management.base import BaseCommand

from texta.settings import ERROR_LOGGER, INFO_LOGGER
from task_manager.models import Task
from task_manager.tasks.task_params import activate_task_worker

# Define max number of background running processes
MAX_RUNNING = 6
# Total minutes allowed since last update in a task
MAX_LAST_UPDATE_MINUTES = 1000


class Command(BaseCommand):

    def _time_out_tasks(self, running_tasks):
        """ Time out tasks

        Uses the last update time as "watch dog" time and mark task
        as failed with timeout if MAX_LAST_UPDATE_MINUTES has passed
        """
        for task in running_tasks:
            now = datetime.now()
            timeout_time = task.last_update + relativedelta(minutes=MAX_LAST_UPDATE_MINUTES)
            # if now passed timeout time
            if now > timeout_time:
                print("-> Task timeout: ", task.id)
                task.update_status(Task.STATUS_FAILED, set_time_completed=True)
                task.update_progress(0, "timeout")

                log_dict = {'task': 'Task Scheduler', 'event': 'time_out_task', 'task_id': task.id}
                logging.getLogger(ERROR_LOGGER).error("Task timed out", extra=log_dict)

    def _execute_task(self, task):
        """ Execute task
        """
        task_type = task.task_type
        task_id = task.id
        worker = activate_task_worker(task_type)
        if worker is None:
            task.update_status(Task.STATUS_FAILED)
            log_dict = {'task': 'Task Scheduler', 'event': 'invalid_task', 'task_type': task_type, 'task_id': task_id}
            logging.getLogger(ERROR_LOGGER).error("Invalid task", extra=log_dict)
            return
        try:
            # Run worker
            worker.run(task_id)
        except Exception as e:
            # Capture generic task error
            task.update_status(Task.STATUS_FAILED)
            log_dict = {'task': 'Task Scheduler', 'event': 'task_execution_error', 'task_type': task_type, 'task_id': task_id}

            logging.getLogger(INFO_LOGGER).info("Task execution error", extra=log_dict)
            logging.getLogger(ERROR_LOGGER).exception(e)

            print(e)

    def handle(self, *args, **options):
        """ Schedule tasks for background execution
        """
        # Get running tasks
        running_tasks = Task.objects.filter(status=Task.STATUS_RUNNING)
        capacity = MAX_RUNNING - len(running_tasks)

        # Allocate queued tasks to running tasks
        queued_tasks = Task.objects.filter(status=Task.STATUS_QUEUED).order_by('last_update')
        print("------------------------------------------------------")
        print("-> Total of queued tasks: ", len(queued_tasks))
        print("-> Total of running tasks: ", len(running_tasks))
        print("-> Current free capacity: ", capacity)
        print("------------------------------------------------------")

        # Mark timed out tasks
        self._time_out_tasks(running_tasks)

        # Check if max running tasks in progress
        if capacity <= 0:
            log_dict = {'task': 'Task Scheduler', 'event': 'max_running_tasks'}
            logging.getLogger(INFO_LOGGER).info("Running max tasks", extra=log_dict)
            return

        # Execute one task from queue
        if len(queued_tasks) > 0:
            task = queued_tasks[0]
            self._execute_task(task)
