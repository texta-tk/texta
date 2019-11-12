from celery.decorators import task

from toolkit.core.task.models import Task
from toolkit.torchtagger.models import TorchTagger
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.tools.show_progress import ShowProgress
from toolkit.base_task import BaseTask

@task(name="torchtagger_train_handler", base=BaseTask)
def torchtagger_train_handler(tagger_id, testing=False):
    # retrieve neurotagger & task objects
    tagger_obj = TorchTagger.objects.get(pk=tagger_id)
    task_object = tagger_obj.task

    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step("scrolling data")
    show_progress.update_view(0)


