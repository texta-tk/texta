import os
import json
import secrets

from celery.decorators import task
from celery import chord
from keras import backend as K

from toolkit.core.task.models import Task
from toolkit.neurotagger.models import Neurotagger
from toolkit.settings import NUM_WORKERS, MODELS_DIR
from toolkit.embedding.phraser import Phraser
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.tools.show_progress import ShowProgress
from toolkit.neurotagger.neurotagger import NeurotaggerWorker
# from toolkit.neurotagger.plots import create_neurotagger_plot


@task(name="neurotagger_train_handler")
def neurotagger_train_handler(neurotagger_id):
    # retrieve neurotagger & task objects
    neurotagger_obj = Neurotagger.objects.get(pk=neurotagger_id)
    task_object = neurotagger_obj.task

    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step("scrolling data")
    show_progress.update_view(0)

    queries = json.loads(neurotagger_obj.queries)

    kwargs = {"neurotagger_id": neurotagger_obj.id}

    return chord((scroll_data.s(query, kwargs=kwargs) for query in queries), train_model.s(kwargs=kwargs))()


@task(name="scroll_data")
def scroll_data(query, kwargs={}):
    neurotagger_obj = Neurotagger.objects.get(pk=kwargs["neurotagger_id"])

    indices = neurotagger_obj.project.indices
    field_data = json.loads(neurotagger_obj.fields)
    fact_values =  json.loads(neurotagger_obj.fact_values)
    maximum_sample_size = neurotagger_obj.maximum_sample_size
    max_seq_len = neurotagger_obj.seq_len

    show_progress = None
    doc_ids = []

    query_samples, query_labels, query_ids = _scroll_multilabel_positives(query, maximum_sample_size, field_data, show_progress, fact_values, max_seq_len, doc_ids)

    return {"query_samples": query_samples, "query_labels": query_labels, "query_ids": query_ids}
    

@task(name="train_model")
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

    for scrolled_samples in scrolled_samples_by_query:
        # TODO: remove duplicates here
        # Are we sure that's the correct thing to to anyway?
        samples += scrolled_samples["query_samples"]
        labels  += scrolled_samples["query_labels"]

    # this temporary i guess?
    multilabel = True

    try:
        assert len(labels) == len(samples), f'X/y are inconsistent lengths: {len(samples)} != {len(labels)}'

        label_names = get_label_names(neurotagger_obj)
        neurotagger = NeurotaggerWorker(neurotagger_obj.id)
        neurotagger.run(samples, labels, show_progress, label_names, multilabel)

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


def _scroll_multilabel_positives(query, maximum_sample_size, field_data, show_progress, fact_values, max_seq_len, already_processed_ids):
    positive_samples = ElasticSearcher(query=query, 
                                       field_data=field_data + ['texta_facts'],
                                       callback_progress=show_progress,
                                       scroll_limit=maximum_sample_size,
                                       ignore_ids=already_processed_ids,
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

        # If the obj has fact_values, get data for a multilabel classifier, else get data for a binary/multiclass classifier
        if neurotagger_obj.fact_values:
            samples, labels = _scroll_multilabel_data(neurotagger_obj, field_data, show_progress)
            multilabel = True
        else:
            samples, labels = _scroll_multiclass_data(json.loads(neurotagger_obj.queries), show_progress, neurotagger_obj, field_data)
            multilabel = False

        assert len(labels) == len(samples), f'X/y are inconsistent lengths: {len(samples)} != {len(labels)}'

        show_progress.update_step('training')
        show_progress.update_view(0)

        label_names = get_label_names(neurotagger_obj)
        neurotagger = NeurotaggerWorker(neurotagger_obj.id)
        neurotagger.run(samples, labels, show_progress, label_names, multilabel)

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


def _scroll_multiclass_data(queries, show_progress, neurotagger_obj, field_data):
    num_queries = len(queries)

    samples = []
    labels = []
    # If there is only 1 query, scroll negative training examples as well
    if len(queries) == 1:
        positive_samples, positive_ids = _scroll_positives(queries[0], neurotagger_obj, field_data, show_progress)
        samples += positive_samples
        # WRAP LABELS IN A LIST, so np.array would automatically turn the shape into (n_samples, n_classes) instead of (n_samples,)
        labels += [[1] for x in range(len(positive_samples))]

        show_progress.update_step('scrolling negatives')
        show_progress.update_view(0)
        negative_samples = _scroll_negatives(neurotagger_obj, field_data, show_progress, positive_ids)
        samples += negative_samples
        labels += [[0] for x in range(len(negative_samples))]

    elif len(queries) > 1:
        for i, query in enumerate(queries):
            show_progress.update_step(f'Scrolling queries ({i}/{num_queries})')
            print(f'{i}/{num_queries} tick')
            show_progress.update_view(0)
            positive_samples, _ = _scroll_positives(query, neurotagger_obj, field_data, show_progress)
            samples += positive_samples
            labels += [[i] for x in range(len(positive_samples))]
    
    return samples, labels


def _scroll_positives(query, neurotagger_obj, field_data, show_progress):
    positive_samples = ElasticSearcher(query=query, 
                                       field_data=field_data,
                                       output='doc_with_id',
                                       callback_progress=show_progress,
                                       scroll_limit=int(neurotagger_obj.maximum_sample_size),
                                       )

    positive_samples = list(positive_samples)
    positive_ids = [doc['_id'] for doc in positive_samples]

    combined_samples = []
    for field in field_data:
        combined_samples += [doc[field] for doc in positive_samples if field in doc]
    return combined_samples, positive_ids


def _scroll_negatives(neurotagger_obj, field_data, show_progress, positive_ids):
    negative_samples = ElasticSearcher(field_data=field_data,
                                       output='doc_with_id',
                                       callback_progress=show_progress,
                                       scroll_limit=int(neurotagger_obj.maximum_sample_size)*int(neurotagger_obj.negative_multiplier),
                                       ignore_ids=positive_ids,
                                       )
    negative_samples = list(negative_samples)
    combined_samples = []
    for field in field_data:
        combined_samples += [doc[field] for doc in negative_samples if field in doc]

    return combined_samples


def get_label_names(neurotagger_obj):
    if neurotagger_obj.fact_values:
        return json.loads(neurotagger_obj.fact_values)
    if neurotagger_obj.query_names:
        return json.loads(neurotagger_obj.query_names)
