import json
import logging
from typing import List, Optional

from celery.decorators import task
from texta_elastic.document import ElasticDocument
from texta_elastic.searcher import ElasticSearcher

from toolkit.base_tasks import TransactionAwareTask
from toolkit.core.task.models import Task
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, ERROR_LOGGER, INFO_LOGGER
from toolkit.summarizer.helpers import process_actions
from toolkit.summarizer.models import Summarizer
from toolkit.summarizer.sumy import Sumy
from toolkit.tools.show_progress import ShowProgress


sumy: Optional[Sumy] = None


def load_sumy():
    global sumy
    if sumy is None:
        sumy = Sumy()


@task(name="start_summarizer_worker", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE, bind=True)
def start_summarizer_worker(self, summarizer_id: int):
    logging.getLogger(INFO_LOGGER).info(f"Starting applying summarizer on the index for model ID: {summarizer_id}")
    summarizer_object = Summarizer.objects.get(pk=summarizer_id)
    task_objects = summarizer_object.tasks.last()
    show_progress = ShowProgress(task_objects, multiplier=1)
    show_progress.update_step('running summarizer')
    show_progress.update_view(0)
    return summarizer_id


@task(name="apply_summarizer_on_index", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE, bind=True)
def apply_summarizer_on_index(self, summarizer_id: int):
    summarizer_object = Summarizer.objects.get(pk=summarizer_id)
    task_object = summarizer_object.tasks.last()
    try:
        load_sumy()
        show_progress = ShowProgress(task_object, multiplier=1)
        show_progress.update_step('scrolling summarizer')

        # Get the necessary fields.
        indices: List[str] = summarizer_object.get_indices()
        field_data: List[str] = json.loads(summarizer_object.fields)
        ratio_data: float[str] = summarizer_object.ratio
        algorithm_data: List[str] = summarizer_object.algorithm

        scroll_size = 100
        searcher = ElasticSearcher(
            query=json.loads(summarizer_object.query),
            indices=indices,
            field_data=field_data,
            output=ElasticSearcher.OUT_RAW,
            callback_progress=show_progress,
            scroll_size=scroll_size,
            scroll_timeout="30m"
        )

        actions = process_actions(searcher, field_data, ratio_data, algorithm=algorithm_data, summarizer_class=sumy, summarizer_id=summarizer_id)

        # Send the data towards Elasticsearch
        ed = ElasticDocument("_all")
        elastic_response = ed.bulk_update(actions=actions)
        return summarizer_id

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise e


@task(name="end_summarizer_task", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE, bind=True)
def end_summarizer_task(self, summarizer_id):
    logging.getLogger(INFO_LOGGER).info(f"Finished applying summarizer on the index for model ID: {summarizer_id}")
    summarizer_object = Summarizer.objects.get(pk=summarizer_id)
    summarizer_object.tasks.last().complete()
    return True
