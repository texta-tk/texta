import json
import logging

import requests
from celery.decorators import task

from toolkit.base_task import BaseTask
from toolkit.core.task.models import Task
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.mlp.models import MLPProcessor
from toolkit.settings import MLP_URL, ERROR_LOGGER
from toolkit.tools.common_utils import grouper
from toolkit.tools.show_progress import ShowProgress


@task(name="start_mlp", base=BaseTask)
def start_mlp(mlp_id):
    # retrieve embedding & task objects
    mlp_object = MLPProcessor.objects.get(pk=mlp_id)
    task_object = mlp_object.task
    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('running mlp')
    show_progress.update_view(0)

    # retrieve indices from project
    indices = json.loads(mlp_object.indices)
    field_data = json.loads(mlp_object.fields)

    searcher = ElasticSearcher(
        query=mlp_object.query,
        indices=indices,
        field_data=field_data,
        output=ElasticSearcher.OUT_RAW,
    )

    for chunk in grouper(100, searcher):

        payload = {
            "docs": [doc["_source"] for doc in chunk],
            "transport_meta": [{"_index": doc["_index"], "_type": doc["_type"], "_id": doc["_id"]} for doc in chunk],
            "fields_to_parse": field_data,
            "analyzers": list(mlp_object.analyzers),
            "transporter": "elasticsearch",
            "task_id": task_object.id,
            "authtoken_hash": task_object.authtoken_hash.hex
        }

        # On the MLP side, 'all' was taken as an option,
        # and is instead the silent default.
        if "all" in payload["analyzers"]:
            del payload["analyzers"]

        url = "{}/{}".format(MLP_URL, "mlp/doc/task")
        response = requests.post(url, json=payload)
        if not response.ok:
            logging.getLogger(ERROR_LOGGER).error(response.text)

    return True

