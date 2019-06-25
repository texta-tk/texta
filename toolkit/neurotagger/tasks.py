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
from toolkit.neurotagger.text_neurotagger import TextNeurotagger
from toolkit.tools.text_processor import TextProcessor
from toolkit.neurotagger.plots import create_neurotagger_plot


@task(name="train_neurotagger")
def train_neurotagger(neurotagger_id):
    # retrieve neurotagger & task objects
    neurotagger_object = Neurotagger.objects.get(pk=neurotagger_id)
    task_object = neurotagger_object.task

    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('scrolling positives')
    show_progress.update_view(0)

    field_data = [ElasticSearcher().core.decode_field_data(field) for field in neurotagger_object.fields]
    field_path_list = [field['field_path'] for field in field_data]

    # add phraser here
    # TODO: use embedding to group together features
    if neurotagger_object.embedding:
        phraser = Phraser(embedding_id=neurotagger_object.embedding.pk)
        phraser.load()
        text_processor = TextProcessor(phraser=phraser, remove_stop_words=True)
    else:
        text_processor = TextProcessor(remove_stop_words=True)

    samples, labels = _scroll_multiclass_data(json.loads(neurotagger_object.queries))

    show_progress.update_step('training')
    show_progress.update_view(0)

    neurotagger = Neurotagger(
        neurotagger_object.model_architecture,
        neurotagger_object.seq_len,
        neurotagger_object.vocab_size,
        neurotagger_object.num_epochs,
        neurotagger_object.validation_split,
    )
    neurotagger.run(samples, labels)

    show_progress.update_step('saving')
    show_progress.update_view(0)

    neurotagger_path = os.path.join(MODELS_DIR, 'neurotagger', f'neurotagger_{neurotagger_id}_{secrets.token_hex(10)}')
    neurotagger.save(neurotagger_path)

    # save model locations
    neurotagger_object.location = json.dumps({'neurotagger': neurotagger_path})
    neurotagger_object.precision = float(neurotagger.statistics['precision'])
    neurotagger_object.recall = float(neurotagger.statistics['recall'])
    neurotagger_object.f1_score = float(neurotagger.statistics['f1_score'])
    neurotagger_object.plot.save(f'{secrets.token_hex(15)}.png', create_neurotagger_plot(neurotagger.model, neurotagger.statistics))
    neurotagger_object.save()


    # declare the job done
    show_progress.update_step('')
    show_progress.update_view(100.0)
    task_object.update_status(Task.STATUS_COMPLETED, set_time_completed=True)
    return True


def _scroll_multiclass_data(queries):
    samples = []
    labels = []

    if len(queries) == 1:
        positive_samples, positive_ids = _scroll_positives(query=queries[0])
        samples += positive_samples
        labels += [1 for x in range(len(positive_samples))]

        show_progress.update_step('scrolling negatives')
        show_progress.update_view(0)
        negative_samples = _scroll_negatives()
        samples += negative_samples
        labels += [0 for x in range(len(negative_samples))]
        
    elif len(queries) > 1:
        for i, query in enumerate(queries):
            positive_samples, _ = _scroll_positives(query=query)
            samples += positive_samples
            labels += [i for x in range(len(positive_samples))]
    
    return samples, labels




def _scroll_positives(query):
    positive_samples = ElasticSearcher(query=json.loads(neurotagger_object.query), 
                                       field_data=field_data,
                                       output='doc_with_id',
                                       callback_progress=show_progress,
                                       scroll_limit=int(neurotagger_object.maximum_sample_size),
                                       text_processor=text_processor
                                       )

    positive_samples = list(positive_samples)
    positive_ids = list([doc['_id'] for doc in positive_samples])
    return positive_samples, positive_ids


def _scroll_negatives():
    negative_samples = ElasticSearcher(field_data=field_data,
                                       output='doc_with_id',
                                       callback_progress=show_progress,
                                       scroll_limit=int(neurotagger_object.maximum_sample_size)*int(neurotagger_object.negative_multiplier),
                                       ignore_ids=positive_ids,
                                       text_processor=text_processor
                                       )

    return list(negative_samples)
