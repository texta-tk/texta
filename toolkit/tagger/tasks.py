from toolkit.core.task.models import Task
from toolkit.tagger.models import Tagger
from toolkit.settings import NUM_WORKERS, MODELS_DIR
from toolkit.embedding.phraser import Phraser
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.tools.show_progress import ShowProgress
from toolkit.tagger.text_tagger import TextTagger
from toolkit.tools.text_processor import TextProcessor
from toolkit.tagger.plots import create_tagger_plot

from celery.decorators import task
import secrets
import json
import os



@task(name="train_tagger")
def train_tagger(tagger_id):
    # retrieve tagger & task objects
    tagger_object = Tagger.objects.get(pk=tagger_id)
    task_object = tagger_object.task

    show_progress = ShowProgress(task_object.id, multiplier=1)
    show_progress.update_step('scrolling positives')
    show_progress.update_view(0)

    field_data = [ElasticSearcher().core.decode_field_data(field) for field in tagger_object.fields]
    field_path_list = [field['field_path'] for field in field_data]

    # add phraser here
    if tagger_object.embedding:
        phraser = Phraser(embedding_id=tagger_object.embedding.pk)
        phraser.load()
        text_processor = TextProcessor(phraser=phraser, remove_stop_words=True)
    else:
        text_processor = TextProcessor(remove_stop_words=True)
    
    # TODO: use embedding to group together features

    positive_samples = ElasticSearcher(query=json.loads(tagger_object.query), 
                                       field_data=field_data,
                                       output='doc_with_id',
                                       callback_progress=show_progress,
                                       scroll_limit=int(tagger_object.maximum_sample_size),
                                       text_processor=text_processor
                                       )

    positive_samples = list(positive_samples)
    positive_ids = list([doc['_id'] for doc in positive_samples])

    show_progress.update_step('scrolling negatives')
    show_progress.update_view(0)
    negative_samples = ElasticSearcher(field_data=field_data,
                                       output='doc_with_id',
                                       callback_progress=show_progress,
                                       scroll_limit=int(tagger_object.maximum_sample_size)*int(tagger_object.negative_multiplier),
                                       ignore_ids=positive_ids,
                                       text_processor=text_processor
                                       )

    negative_samples = list(negative_samples)

    show_progress.update_step('training')
    show_progress.update_view(0)

    tagger = TextTagger(tagger_id)
    tagger.train(positive_samples, negative_samples, field_list=field_path_list, classifier=tagger_object.classifier, vectorizer=tagger_object.vectorizer)

    show_progress.update_step('saving')
    show_progress.update_view(0)

    tagger_path = os.path.join(MODELS_DIR, 'tagger', 'tagger_'+str(tagger_id))
    tagger.save(tagger_path)

    # save model locations
    tagger_object.location = json.dumps({'tagger': tagger_path})
    tagger_object.precision = float(tagger.statistics['precision'])
    tagger_object.recall = float(tagger.statistics['recall'])
    tagger_object.f1_score = float(tagger.statistics['f1_score'])
    tagger_object.plot.save('{}.png'.format(secrets.token_hex(15)), create_tagger_plot(tagger.model, tagger.statistics))
    tagger_object.save()


    # declare the job done
    show_progress.update_step('')
    show_progress.update_view(100.0)
    task_object.update_status(Task.STATUS_COMPLETED, set_time_completed=True)
    return True
