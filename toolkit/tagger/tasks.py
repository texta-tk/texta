import os
import json
import secrets

from celery.decorators import task

from toolkit.core.task.models import Task
from toolkit.tagger.models import Tagger
from toolkit.settings import NUM_WORKERS, MODELS_DIR
from toolkit.embedding.phraser import Phraser
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.tools.show_progress import ShowProgress
from toolkit.tagger.text_tagger import TextTagger
from toolkit.tools.text_processor import TextProcessor
from toolkit.tagger.plots import create_tagger_plot


@task(name="train_tagger")
def train_tagger(tagger_id):
    # retrieve tagger & task objects
    tagger_object = Tagger.objects.get(pk=tagger_id)
    task_object = tagger_object.task

    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('scrolling positives')
    show_progress.update_view(0)

    try:
        # decode field data
        #field_data = [ElasticSearcher().core.decode_field_data(field) for field in tagger_object.fields]
        #field_path_list = [field['field_path'] for field in field_data]

        # add phraser and stop words
        stop_words = json.loads(tagger_object.stop_words)
        if tagger_object.embedding:
            phraser = Phraser(embedding_id=tagger_object.embedding.pk)
            phraser.load()
            text_processor = TextProcessor(phraser=phraser, remove_stop_words=True, custom_stop_words=stop_words)
        else:
            text_processor = TextProcessor(remove_stop_words=True, custom_stop_words=stop_words)

        positive_samples = ElasticSearcher(query=json.loads(tagger_object.query), 
                                        field_data=json.loads(tagger_object.fields),
                                        output='doc_with_id',
                                        callback_progress=show_progress,
                                        scroll_limit=int(tagger_object.maximum_sample_size),
                                        text_processor=text_processor
                                        )

        positive_samples = list(positive_samples)
        positive_ids = list([doc['_id'] for doc in positive_samples])

        show_progress.update_step('scrolling negatives')
        show_progress.update_view(0)
        negative_samples = ElasticSearcher(field_data=json.loads(tagger_object.fields),
                                        output='doc_with_id',
                                        callback_progress=show_progress,
                                        scroll_limit=int(tagger_object.maximum_sample_size)*int(tagger_object.negative_multiplier),
                                        ignore_ids=positive_ids,
                                        text_processor=text_processor
                                        )

        negative_samples = list(negative_samples)

        show_progress.update_step('training')
        show_progress.update_view(0)

        # train model
        tagger = TextTagger(tagger_id)
        tagger.train(positive_samples,
                     negative_samples,
                     field_list=list(set([field['path'] for field in json.loads(tagger_object.fields)])),
                     classifier=tagger_object.classifier,
                     vectorizer=tagger_object.vectorizer)

        show_progress.update_step('saving')
        show_progress.update_view(0)

        tagger_path = os.path.join(MODELS_DIR, 'tagger', f'tagger_{tagger_id}_{secrets.token_hex(10)}')
        tagger.save(tagger_path)

        # save model locations
        tagger_object.location = json.dumps({'tagger': tagger_path})
        tagger_object.precision = float(tagger.statistics['precision'])
        tagger_object.recall = float(tagger.statistics['recall'])
        tagger_object.f1_score = float(tagger.statistics['f1_score'])
        tagger_object.num_features = tagger.statistics['num_features']
        tagger_object.plot.save(f'{secrets.token_hex(15)}.png', create_tagger_plot(tagger.statistics))
        tagger_object.save()

        # declare the job done
        show_progress.update_step('')
        show_progress.update_view(100.0)
        task_object.update_status(Task.STATUS_COMPLETED, set_time_completed=True)
        return True

    except Exception as e:
        # declare the job failed
        show_progress.update_errors(e)
        task_object.update_status(Task.STATUS_FAILED)
        return False
