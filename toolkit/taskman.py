import os
import pathlib

from celery import Celery


os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'toolkit.settings')
app = Celery('taskman')

# Using a string here means the worker will not have to
# pickle the object when using Windows.
app.config_from_object('django.conf:settings')
app.autodiscover_tasks()
for path in pathlib.Path("toolkit/elastic/").rglob("*"):
    if path.is_dir():
        app.autodiscover_tasks([f"toolkit.elastic.{path.name}"])

# Discover all the periodic tasks for maintenance.
app.autodiscover_tasks(['toolkit.beat_tasks'])


@app.task(bind=True)
def debug_task(self):
    print('Request: {0!r}'.format(self.request))
