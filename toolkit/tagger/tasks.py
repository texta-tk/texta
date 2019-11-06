import os
import json
import secrets

from celery.decorators import task

from toolkit.core.task.models import Task
from toolkit.tagger.models import Tagger, TaggerGroup
from toolkit.settings import NUM_WORKERS, MODELS_DIR
from toolkit.embedding.phraser import Phraser
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.tools.show_progress import ShowProgress
from toolkit.tagger.text_tagger import TextTagger
from toolkit.tools.text_processor import TextProcessor
from toolkit.tagger.plots import create_tagger_plot
from toolkit.base_task import BaseTask
from toolkit.tools.mlp_analyzer import MLPAnalyzer
from toolkit.elastic.feedback import Feedback


@task(name="create_tagger_objects", base=BaseTask)
def create_tagger_objects(tagger_group_id, tagger_serializer, tags, tag_queries):
    # retrieve Tagger Group object
    tagger_group_object = TaggerGroup.objects.get(pk=tagger_group_id)
    # create tagger objects
    taggers_to_create = []
    for i,tag in enumerate(tags):
        tagger_data = tagger_serializer.copy()
        tagger_data.update({'query': json.dumps(tag_queries[i])})
        tagger_data.update({'description': tag})
        tagger_data.update({'fields': json.dumps(tagger_data['fields'])})
        created_tagger = Tagger.objects.create(**tagger_data,
            author=tagger_group_object.author,
            project=tagger_group_object.project)
        taggers_to_create.append(created_tagger)
    # create tagger objects
    tagger_group_object.taggers.add(*taggers_to_create)
    tagger_group_object.save()
    return True


def get_data_samples(tagger_object, text_processor, show_progress, indices, field_data):
    # change status to scrolling negative feedback
    show_progress.update_step('scrolling positive feedback')
    show_progress.update_view(0)
    # iterator for retrieving positive feedback sample
    positive_feedback_sample = Feedback(
        tagger_object.project.pk,
        model_pk=tagger_object.pk,
        model_type='tagger',
        prediction_to_match='true',
        text_processor=text_processor,
        callback_progress=show_progress,
    )
    positive_feedback_sample = list(positive_feedback_sample)

    # change status to scrolling positive sample
    show_progress.update_step('scrolling positive sample')
    show_progress.update_view(0)
    # iterator for retrieving positive sample by query
    positive_sample = ElasticSearcher(
        query=json.loads(tagger_object.query),
        indices=indices,
        field_data=field_data,
        output=ElasticSearcher.OUT_DOC_WITH_ID,
        callback_progress=show_progress,
        scroll_limit=int(tagger_object.maximum_sample_size)-len(positive_feedback_sample),
        text_processor=text_processor
    )

    # iterators into lists and combine positive samples into one
    positive_sample = positive_feedback_sample+list(positive_sample)
    positive_ids = list([doc['_id'] for doc in positive_sample])

    # change status to scrolling negative feedback
    show_progress.update_step('scrolling negative feedback')
    show_progress.update_view(0)
    # iterator for retrieving negative feedback sample
    negative_feedback_sample = Feedback(
        tagger_object.project.pk,
        model_pk=tagger_object.pk,
        model_type='tagger',
        prediction_to_match='false',
        text_processor=text_processor,
        callback_progress=show_progress,
    )
    # iterator to list
    negative_feedback_sample = list(negative_feedback_sample)

    # change status to scrolling negative sample
    show_progress.update_step('scrolling negative sample')
    show_progress.update_view(0)
    # iterator for retrieving negative examples
    negative_sample = ElasticSearcher(
        indices=indices,
        field_data=field_data,
        output=ElasticSearcher.OUT_DOC_WITH_ID,
        callback_progress=show_progress,
        scroll_limit=(len(positive_sample)-len(negative_feedback_sample))*int(tagger_object.negative_multiplier),
        ignore_ids=positive_ids,
        text_processor=text_processor
    )
    # combine negative samples into one
    negative_sample = negative_feedback_sample+list(negative_sample)

    return positive_sample, negative_sample


@task(name="train_tagger", base=BaseTask)
def train_tagger(tagger_id):
    # retrieve tagger & task objects
    tagger_object = Tagger.objects.get(pk=tagger_id)
    task_object = tagger_object.task
    # create progress object
    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('scrolling positives')
    show_progress.update_view(0)
    
    try:
        # retrieve indices & field data from project 
        indices = tagger_object.project.indices
        field_data = json.loads(tagger_object.fields)
        stop_words = json.loads(tagger_object.stop_words)
        # load embedding and create text processor
        if tagger_object.embedding:
            phraser = Phraser(embedding_id=tagger_object.embedding.pk)
            phraser.load()
            text_processor = TextProcessor(phraser=phraser, remove_stop_words=True, custom_stop_words=stop_words)
        else:
            text_processor = TextProcessor(remove_stop_words=True, custom_stop_words=stop_words)
        # retrieve training samples
        positive_sample, negative_sample = get_data_samples(tagger_object, text_processor, show_progress, indices, field_data)
        # update status to training
        show_progress.update_step('training')
        show_progress.update_view(0)
        # train model
        tagger = TextTagger(tagger_id)
        tagger.train(
            positive_sample,
            negative_sample,
            field_list=json.loads(tagger_object.fields),
            classifier=tagger_object.classifier,
            vectorizer=tagger_object.vectorizer
        )
        # update status to saving
        show_progress.update_step('saving')
        show_progress.update_view(0)
        # save tagger to disk
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
        phraser = global_phraser_cache.get_model(tagger.embedding)
        text_processor = TextProcessor(phraser=phraser, remove_stop_words=True, custom_stop_words=stop_words, lemmatizer=lemmatizer)
    else:
        text_processor = TextProcessor(remove_stop_words=True, custom_stop_words=stop_words, lemmatizer=lemmatizer)
    # load tagger
    tagger = global_tagger_cache.get_model(tagger)
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
