import json
import logging
import os
import re
import secrets

from celery.decorators import task

from toolkit.base_task import BaseTask
from toolkit.core.task.models import Task
from toolkit.elastic.data_sample import DataSample
from toolkit.elastic.feedback import Feedback
from toolkit.elastic.models import Index
from toolkit.embedding.phraser import Phraser
from toolkit.helper_functions import get_indices_from_object
from toolkit.settings import ERROR_LOGGER, INFO_LOGGER
from toolkit.tagger.models import Tagger, TaggerGroup
from toolkit.tagger.plots import create_tagger_plot
from toolkit.tagger.text_tagger import TextTagger
from toolkit.tools.mlp_analyzer import MLPAnalyzer
from toolkit.tools.show_progress import ShowProgress
from toolkit.tools.text_processor import TextProcessor


def create_tagger_batch(tagger_group_id, taggers_to_create):
    """Creates Tagger objects from list of tagger data and saves into tagger group object."""
    # retrieve Tagger Group object

    tagger_group_object = TaggerGroup.objects.get(pk=tagger_group_id)
    # iterate through batch
    logging.getLogger(INFO_LOGGER).info(f"Creating {len(taggers_to_create)} taggers for TaggerGroup ID: {tagger_group_id}!")
    for tagger_data in taggers_to_create:
        indices = [index["name"] for index in tagger_data["indices"]]
        indices = tagger_group_object.project.filter_from_indices(indices)
        tagger_data.pop("indices")

        created_tagger = Tagger.objects.create(
            **tagger_data,
            author=tagger_group_object.author,
            project=tagger_group_object.project
        )

        for index in Index.objects.filter(name__in=indices, is_open=True):
            created_tagger.indices.add(index)


        # add and save
        tagger_group_object.taggers.add(created_tagger)
        tagger_group_object.save()

        created_tagger.train()


@task(name="create_tagger_objects", base=BaseTask)
def create_tagger_objects(tagger_group_id, tagger_serializer, tags, tag_queries, batch_size=100):
    """Task for creating Tagger objects inside Tagger Group to prevent database timeouts."""
    # create tagger objects
    logging.getLogger(INFO_LOGGER).info(f"Starting task 'create_tagger_objects' for TaggerGroup with ID: {tagger_group_id}!")

    taggers_to_create = []
    for i, tag in enumerate(tags):
        tagger_data = tagger_serializer.copy()
        tagger_data.update({'query': json.dumps(tag_queries[i])})
        tagger_data.update({'description': tag})
        tagger_data.update({'fields': json.dumps(tagger_data['fields'])})
        taggers_to_create.append(tagger_data)
        # if batch size reached, save result
        if len(taggers_to_create) >= batch_size:
            create_tagger_batch(tagger_group_id, taggers_to_create)
            taggers_to_create = []
    # if any taggers remaining
    if taggers_to_create:
        # create tagger objects of remaining items
        create_tagger_batch(tagger_group_id, taggers_to_create)

    logging.getLogger(INFO_LOGGER).info(f"Completed task 'create_tagger_objects' for TaggerGroup with ID: {tagger_group_id}!")
    return True


@task(name="train_tagger", base=BaseTask)
def train_tagger(tagger_id):
    """Task for training Text Tagger."""
    logging.getLogger(INFO_LOGGER).info(f"Starting task 'train_tagger' for tagger with ID: {tagger_id}!")

    # retrieve tagger & task objects
    tagger_object = Tagger.objects.get(pk=tagger_id)
    task_object = tagger_object.task
    # create progress object
    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('scrolling positives')
    show_progress.update_view(0)

    try:
        # retrieve indices & field data
        indices = get_indices_from_object(tagger_object)
        field_data = json.loads(tagger_object.fields)

        # split stop words by space or newline
        stop_words = re.split(' |\n|\r\n', tagger_object.stop_words)

        # remove empty strings
        stop_words = [stop_word for stop_word in stop_words if stop_word]

        # load embedding and create text processor
        if tagger_object.embedding:
            logging.getLogger(INFO_LOGGER).info(f"Applying embedding ID {tagger_object.embedding.id} for tagger with ID {tagger_object.pk}!")
            phraser = Phraser(embedding_id=tagger_object.embedding.pk)
            phraser.load()
            text_processor = TextProcessor(phraser=phraser, remove_stop_words=True, custom_stop_words=stop_words)
        else:
            text_processor = TextProcessor(remove_stop_words=True, custom_stop_words=stop_words)

        # create Datasample object for retrieving positive and negative sample
        data_sample = DataSample(
            tagger_object,
            indices=indices,
            field_data=field_data,
            show_progress=show_progress,
            text_processor=text_processor
        )

        # update status to training
        show_progress.update_step('training')
        show_progress.update_view(0)

        # train model
        tagger = TextTagger(tagger_id)
        logging.getLogger(INFO_LOGGER).info(f"Starting training process for tagger ID: {tagger_id}")
        tagger.train(
            data_sample,
            field_list=json.loads(tagger_object.fields),
            classifier=tagger_object.classifier,
            vectorizer=tagger_object.vectorizer
        )

        # update status to saving
        show_progress.update_step('saving')
        show_progress.update_view(0)

        # save tagger to disk
        tagger_path = tagger_object.generate_name("tagger")
        tagger.save(tagger_path)

        tagger_object.model.name = tagger_path
        tagger_object.precision = float(tagger.statistics['precision'])
        tagger_object.recall = float(tagger.statistics['recall'])
        tagger_object.f1_score = float(tagger.statistics['f1_score'])
        tagger_object.num_features = tagger.statistics['num_features']
        tagger_object.num_positives = tagger.statistics['num_positives']
        tagger_object.num_negatives = tagger.statistics['num_negatives']
        tagger_object.model_size = round(float(os.path.getsize(tagger_path)) / 1000000, 1)  # bytes to mb
        tagger_object.plot.save(f'{secrets.token_hex(15)}.png', create_tagger_plot(tagger.statistics))
        tagger_object.save()

        # declare the job done
        task_object.complete()
        logging.getLogger(INFO_LOGGER).info(f"Completed task 'train_tagger' for tagger with ID: {tagger_id}!")
        return True

    except Exception as e:
        # declare the job failed
        logging.getLogger(ERROR_LOGGER).exception(e)
        show_progress.update_errors(e)
        task_object.update_status(Task.STATUS_FAILED)
        raise


@task(name="apply_tagger", base=BaseTask)
def apply_tagger(tagger_id, text, input_type='text', lemmatize=False, feedback=None):
    """Task for applying tagger to text."""
    logging.getLogger(INFO_LOGGER).info(f"Starting task 'apply_tagger' for tagger with ID: {tagger_id} with params (input_type : {input_type}, lemmatize: {lemmatize}, feedback: {feedback})!")

    # get tagger object
    tagger_object = Tagger.objects.get(pk=tagger_id)
    # get lemmatizer if needed
    lemmatizer = None
    if lemmatize:
        lemmatizer = MLPAnalyzer()
    # create text processor object for tagger
    stop_words = tagger_object.stop_words.split(' ')
    if tagger_object.embedding:
        logging.getLogger(INFO_LOGGER).info(f"Applying embedding ID {tagger_object.embedding.id} for tagger with ID {tagger_object.pk}!")
        phraser = Phraser(tagger_object.embedding.id)
        phraser.load()
        text_processor = TextProcessor(phraser=phraser, remove_stop_words=True, custom_stop_words=stop_words, lemmatizer=lemmatizer)
    else:
        text_processor = TextProcessor(remove_stop_words=True, custom_stop_words=stop_words, lemmatizer=lemmatizer)
    # load tagger
    tagger = TextTagger(tagger_id)
    tagger.load()
    # if not loaded return None
    if not tagger:
        return None
    # add text processor
    tagger.add_text_processor(text_processor)
    # check input type
    if input_type == 'doc':
        logging.getLogger(INFO_LOGGER).info(f"Tagging document with content: {text}!")
        tagger_result = tagger.tag_doc(text)
    else:
        logging.getLogger(INFO_LOGGER).info(f"Tagging text with content: {text}!")
        tagger_result = tagger.tag_text(text)

    # check if prediction positive
    decision = bool(tagger_result[0])
    # create output dict
    prediction = {'tag': tagger.description, 'probability': tagger_result[1], 'tagger_id': tagger_id, 'result': decision}

    # add feedback if asked
    if feedback:
        logging.getLogger(INFO_LOGGER).info(f"Adding feedback for Tagger id: {tagger_object.pk}")
        project_pk = tagger_object.project.pk
        feedback_object = Feedback(project_pk, model_object=tagger_object)
        feedback_id = feedback_object.store(text, decision)
        feedback_url = f'/projects/{project_pk}/taggers/{tagger_object.pk}/feedback/'
        prediction['feedback'] = {'id': feedback_id, 'url': feedback_url}

    logging.getLogger(INFO_LOGGER).info(f"Completed task 'apply_tagger' for tagger with ID: {tagger_id}!")
    return prediction
