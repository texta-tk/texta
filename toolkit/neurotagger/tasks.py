import os
import json
import secrets

from celery.decorators import task

from toolkit.core.task.models import Task
from toolkit.neurotagger.models import Neurotagger
from toolkit.settings import NUM_WORKERS, MODELS_DIR
from toolkit.embedding.phraser import Phraser
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.tools.show_progress import ShowProgress
from toolkit.neurotagger.neurotagger import NeurotaggerWorker
from toolkit.tools.text_processor import TextProcessor
# from toolkit.neurotagger.plots import create_neurotagger_plot

@task(name="train_neurotagger")
def train_neurotagger(neurotagger_id):
    # retrieve neurotagger & task objects
    neurotagger_obj = Neurotagger.objects.get(pk=neurotagger_id)
    task_object = neurotagger_obj.task

    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('scrolling positives')
    show_progress.update_view(0)
    

    try:
        # retrieve indices & field data from project 
        indices = neurotagger_obj.project.indices
        field_data = json.loads(neurotagger_obj.fields)


        # add phraser here
        # TODO: use embedding to group together features
        if neurotagger_obj.embedding:
            phraser = Phraser(embedding_id=neurotagger_obj.embedding.pk)
            phraser.load()
            text_processor = TextProcessor(phraser=phraser, remove_stop_words=True)
        else:
            text_processor = TextProcessor(remove_stop_words=True)

        samples, labels = _scroll_multiclass_data(json.loads(neurotagger_obj.queries), show_progress, neurotagger_obj, field_data, text_processor)
        show_progress.update_step('training')
        show_progress.update_view(0)

        neurotagger = NeurotaggerWorker(neurotagger_obj.id)
        neurotagger.run(samples, labels, show_progress)

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



def _scroll_multiclass_data(queries, show_progress, neurotagger_obj, field_data, text_processor):
    samples = []
    labels = []
    # If there is only 1 query, scroll negative training examples as well
    if len(queries) == 1:
        positive_samples, positive_ids = _scroll_positives(queries[0], neurotagger_obj, field_data, show_progress, text_processor)
        samples += positive_samples
        labels += [1 for x in range(len(positive_samples))]

        show_progress.update_step('scrolling negatives')
        show_progress.update_view(0)
        negative_samples = _scroll_negatives(neurotagger_obj, field_data, show_progress, positive_ids, text_processor)
        samples += negative_samples
        labels += [0 for x in range(len(negative_samples))]

    elif len(queries) > 1:
        for i, query in enumerate(queries):
            positive_samples, _ = _scroll_positives(query, neurotagger_obj, field_data, show_progress, text_processor)
            samples += positive_samples
            labels += [i for x in range(len(positive_samples))]
    
    return samples, labels


def _scroll_positives(query, neurotagger_obj, field_data, show_progress, text_processor):
    positive_samples = ElasticSearcher(query=query, 
                                       field_data=field_data,
                                       output='doc_with_id',
                                       callback_progress=show_progress,
                                       scroll_limit=int(neurotagger_obj.maximum_sample_size),
                                       text_processor=text_processor
                                       )

    positive_samples = list(positive_samples)
    positive_ids = [doc['_id'] for doc in positive_samples]

    combined_samples = []
    for field in field_data:
        combined_samples += [doc[field] for doc in positive_samples]
    return combined_samples, positive_ids


def _scroll_negatives(neurotagger_obj, field_data, show_progress, positive_ids, text_processor):
    negative_samples = ElasticSearcher(field_data=field_data,
                                       output='doc_with_id',
                                       callback_progress=show_progress,
                                       scroll_limit=int(neurotagger_obj.maximum_sample_size)*int(neurotagger_obj.negative_multiplier),
                                       ignore_ids=positive_ids,
                                       text_processor=text_processor
                                       )
    negative_samples = list(negative_samples)
    combined_samples = []
    for field in field_data:
        combined_samples += [doc[field] for doc in negative_samples]

    return combined_samples
