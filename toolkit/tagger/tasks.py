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
from toolkit.base_task import BaseTask
from toolkit.tools.mlp_analyzer import MLPAnalyzer


@task(name="train_tagger", base=BaseTask)
def train_tagger(tagger_id):
    # retrieve tagger & task objects
    tagger_object = Tagger.objects.get(pk=tagger_id)
    task_object = tagger_object.task

    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('scrolling positives')
    show_progress.update_view(0)

    try:
        # retrieve indices & field data from project 
        indices = tagger_object.project.indices
        field_data = json.loads(tagger_object.fields)
        
        # add phraser and stop words
        stop_words = json.loads(tagger_object.stop_words)
        if tagger_object.embedding:
            phraser = Phraser(embedding_id=tagger_object.embedding.pk)
            phraser.load()
            text_processor = TextProcessor(phraser=phraser, remove_stop_words=True, custom_stop_words=stop_words)
        else:
            text_processor = TextProcessor(remove_stop_words=True, custom_stop_words=stop_words)

        positive_samples = ElasticSearcher(
            query=json.loads(tagger_object.query),
            indices=indices,
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
        negative_samples = ElasticSearcher(
            indices=indices,
            field_data=field_data,
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
                     field_list=json.loads(tagger_object.fields),
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
        raise


@task(name="apply_tagger", base=BaseTask)
def apply_tagger(text, tagger_id, input_type, lemmatize=False):
    from toolkit.tagger.tagger_views import global_tagger_cache
    from toolkit.embedding.views import global_phraser_cache
    
    # get tagger object
    tagger = Tagger.objects.get(pk=tagger_id)

    # get lemmatizer if needed
    lemmatizer = None
    if lemmatize:
        lemmatizer = MLPAnalyzer()
    
    # create text processor object for tagger
    stop_words = json.loads(tagger.stop_words)
    if tagger.embedding:
        phraser = global_phraser_cache.get_model(tagger.embedding.pk)
        text_processor = TextProcessor(phraser=phraser, remove_stop_words=True, custom_stop_words=stop_words, lemmatizer=lemmatizer)
    else:
        text_processor = TextProcessor(remove_stop_words=True, custom_stop_words=stop_words, lemmatizer=lemmatizer)
    
    # load tagger
    tagger = global_tagger_cache.get_model(tagger_id)
    if not tagger:
        return None
    
    # check input type
    if input_type == 'doc':
        tagger_result = tagger.tag_doc(text)
    else:
        tagger_result = tagger.tag_text(text)

    # check if prediction positive
    decision = bool(tagger_result[0])
    if not decision:
        return None
    
    # return tag info
    return {'tag': tagger.description, 'probability': tagger_result[1], 'tagger_id': tagger_id}
