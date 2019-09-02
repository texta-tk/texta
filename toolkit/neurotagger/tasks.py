import os
import json
import secrets

from celery.decorators import task
from keras import backend as K

from toolkit.core.task.models import Task
from toolkit.neurotagger.models import Neurotagger
from toolkit.settings import MODELS_DIR
from toolkit.embedding.phraser import Phraser
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.tools.show_progress import ShowProgress
from toolkit.neurotagger.neurotagger import NeurotaggerWorker
# from toolkit.neurotagger.plots import create_neurotagger_plot

@task(name="train_neurotagger")
def train_neurotagger(neurotagger_id):
    # retrieve neurotagger & task objects
    neurotagger_obj = Neurotagger.objects.get(pk=neurotagger_id)
    task_object = neurotagger_obj.task
    show_progress = ShowProgress(task_object, multiplier=1)

    try:
        # retrieve indices & field data from project 
        indices = neurotagger_obj.project.indices
        field_data = json.loads(neurotagger_obj.fields)

        show_progress.update_step('scrolling data')
        show_progress.update_view(0)

        samples, labels = _scroll_multilabel_data(neurotagger_obj, field_data, show_progress)

        assert len(labels) == len(samples), f'X/y are inconsistent lengths: {len(samples)} != {len(labels)}'

        show_progress.update_step('training')
        show_progress.update_view(0)

        label_names = get_label_names(neurotagger_obj)
        neurotagger = NeurotaggerWorker(neurotagger_obj.id)
        neurotagger.run(samples, labels, show_progress, label_names)

        # declare the job done
        show_progress.update_step('')
        show_progress.update_view(100.0)
        task_object.update_status(Task.STATUS_COMPLETED, set_time_completed=True)
        return True

    except Exception as e:
        import traceback
        print(traceback.format_exc())
        # declare the job failed
        show_progress.update_errors(e)
        task_object.update_status(Task.STATUS_FAILED)
        return False
    finally:
        # Clear session/release memory after training and saving
        K.clear_session()


def _scroll_multilabel_data(neurotagger_obj, field_data, show_progress):
    queries = json.loads(neurotagger_obj.queries)
    fact_values =  json.loads(neurotagger_obj.fact_values)
    maximum_sample_size = neurotagger_obj.maximum_sample_size
    max_seq_len = neurotagger_obj.seq_len
    num_queries = len(queries)

    samples = []
    labels = []
    doc_ids = []
    for i, query in enumerate(queries):
        # To not ignore documents already parsed
        print(f'{i}/{num_queries} tick')        
        show_progress.update_step(f'Scrolling data for facts ({i}/{num_queries})')
        show_progress.update_view(0)
        query_samples, query_labels, query_ids = _scroll_multilabel_positives(query, maximum_sample_size, field_data, show_progress, fact_values, max_seq_len, doc_ids)
        samples += query_samples
        labels += query_labels
        doc_ids += query_ids

    return samples, labels


def _scroll_multilabel_positives(query, maximum_sample_size, field_data, show_progress, fact_values, max_seq_len, already_processed_ids):
    positive_samples = ElasticSearcher(
        query=query, 
        field_data=field_data + ['texta_facts'],
        callback_progress=show_progress,
        scroll_limit=maximum_sample_size,
        ignore_ids=set(already_processed_ids),
    )

    positive_samples = list(positive_samples)
    query_ids = [doc['_id'] for doc in positive_samples]

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

    return combined_samples, labels, query_ids


def get_label_names(neurotagger_obj):
    if neurotagger_obj.fact_values:
        return json.loads(neurotagger_obj.fact_values)
    if neurotagger_obj.query_names:
        return json.loads(neurotagger_obj.query_names)
