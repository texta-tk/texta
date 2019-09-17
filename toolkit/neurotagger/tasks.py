import os
import json
import secrets

from celery.decorators import task
from celery import chord
from keras import backend as K

from toolkit.core.task.models import Task
from toolkit.neurotagger.models import Neurotagger
from toolkit.settings import MODELS_DIR
from toolkit.embedding.phraser import Phraser
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.tools.show_progress import ShowProgress
from toolkit.neurotagger.neurotagger import NeurotaggerWorker
from toolkit.base_task import BaseTask

@task(name="neurotagger_train_handler", base=BaseTask)
def neurotagger_train_handler(neurotagger_id, testing=False):
    # retrieve neurotagger & task objects
    neurotagger_obj = Neurotagger.objects.get(pk=neurotagger_id)
    task_object = neurotagger_obj.task

    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step("scrolling data")
    show_progress.update_view(0)

    queries = json.loads(neurotagger_obj.queries)
    num_queries = len(queries)

    kwargs = {"neurotagger_id": neurotagger_obj.id, "num_queries": num_queries}
    task_worker = chord((scroll_data.s(query, kwargs=kwargs) for query in queries), train_model.s(kwargs=kwargs))
    if not testing:
        return task_worker()

    return task_worker


@task(name="scroll_data", base=BaseTask)
def scroll_data(query, kwargs={}):
    neurotagger_obj = Neurotagger.objects.get(pk=kwargs["neurotagger_id"])
    num_queries = kwargs["num_queries"]

    indices = neurotagger_obj.project.indices
    field_data = json.loads(neurotagger_obj.fields)
    fact_values =  json.loads(neurotagger_obj.fact_values)
    maximum_sample_size = neurotagger_obj.maximum_sample_size
    max_seq_len = neurotagger_obj.seq_len


    doc_ids = []
    query_samples, query_labels, query_ids = _scroll_multilabel_positives(query, maximum_sample_size, field_data, fact_values, max_seq_len)
    neurotagger_obj.task.update_process_iteration(total=num_queries, step_prefix='Scrolling queries')
    print(f'TICK {neurotagger_obj.task.num_processed} / {num_queries}')
    return {"query_samples": query_samples, "query_labels": query_labels, "query_ids": query_ids}


@task(name="train_model", base=BaseTask)
def train_model(scrolled_samples_by_query, kwargs={}):
    # retrieve neurotagger & task objects
    neurotagger_obj = Neurotagger.objects.get(pk=kwargs["neurotagger_id"])
    task_object = neurotagger_obj.task
    # update progress step to training
    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('training')
    show_progress.update_view(0)

    # samples & labels for the model
    samples = []
    labels  = []

    # dict to track duplicates
    seen_doc_ids = {}

    for scrolled_samples in scrolled_samples_by_query:
        for i, doc_id in enumerate(scrolled_samples["query_ids"]):
            if doc_id not in seen_doc_ids:
                samples.append(scrolled_samples["query_samples"][i])
                labels.append(scrolled_samples["query_labels"][i])
                seen_doc_ids[doc_id] = True


    try:
        assert len(labels) == len(samples), f'X/y are inconsistent lengths: {len(samples)} != {len(labels)}'
        label_names = json.loads(neurotagger_obj.fact_values)
        neurotagger = NeurotaggerWorker(neurotagger_obj.id)
        neurotagger.run(samples, labels, show_progress, label_names)

        # declare the job done
        show_progress.update_step('')
        show_progress.update_view(100.0)
        task_object.update_status(Task.STATUS_COMPLETED, set_time_completed=True)

    except Exception as e:
        # declare the job failed
        show_progress.update_errors(f"training failed: {e}")
        task_object.update_status(Task.STATUS_FAILED)
        return False
    finally:
        # Clear session/release memory after training and saving
        K.clear_session()

    return True


def _scroll_multilabel_positives(query, maximum_sample_size, field_data, fact_values, max_seq_len):
    positive_samples = ElasticSearcher(query=query, 
                                       field_data=field_data + ['texta_facts'],
                                       scroll_limit=maximum_sample_size,
                                       )
    query_ids = []
    combined_samples = []
    labels = []
    for doc in positive_samples:
        combined_doc = ''
        # Features
        for field in field_data:
            if field in doc:
                # Combine data from multiple fields into one doc
                # separate by newlines and 'xxtextadocend' token
                combined_doc += doc[field] + ' xxtextadocend '
        if combined_doc:
            # Crop document as there is no need for the post-crop data
            combined_doc = combined_doc[0:max_seq_len]
            combined_samples.append(combined_doc)
            # Add labels only if document included
            doc_facts = set([fact['str_val'] for fact in doc['texta_facts']])
            labels.append([1 if x in doc_facts else 0 for x in fact_values])
            # Add doc id
            query_ids.append(doc['_id'])
    return combined_samples, labels, query_ids
