import json
import logging
import os
import pathlib
import re
import secrets

from texta_tagger.tagger import Tagger as TextTagger
from texta_tools.text_processor import TextProcessor
from texta_tools.mlp_analyzer import get_mlp_analyzer
from texta_tools.embedding import Phraser, W2VEmbedding

from celery.decorators import task
from toolkit.base_tasks import BaseTask, TransactionAwareTask
from toolkit.core.task.models import Task
from toolkit.elastic.data_sample import DataSample
from toolkit.elastic.feedback import Feedback
from toolkit.elastic.models import Index
from toolkit.helper_functions import get_indices_from_object
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, ERROR_LOGGER, INFO_LOGGER, MEDIA_URL
from toolkit.tagger.models import Tagger, TaggerGroup
from toolkit.tagger.plots import create_tagger_plot
from toolkit.tools.show_progress import ShowProgress


def create_tagger_batch(tagger_group_id, taggers_to_create):
    """Creates Tagger objects from list of tagger data and saves into tagger group object."""
    # retrieve Tagger Group object
    tagger_group_object = TaggerGroup.objects.get(pk=tagger_group_id)
    # iterate through batch
    logging.getLogger(INFO_LOGGER).info(f"Creating {len(taggers_to_create)} taggers for TaggerGroup ID: {tagger_group_id}!")
    for tagger_data in taggers_to_create:
        indices = [index["name"] for index in tagger_data["indices"]]
        indices = tagger_group_object.project.get_available_or_all_project_indices(indices)
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
        # train
        created_tagger.train()


@task(name="create_tagger_objects", base=BaseTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def create_tagger_objects(tagger_group_id, tagger_serializer, tags, tag_queries, batch_size=100):
    """Task for creating Tagger objects inside Tagger Group to prevent database timeouts."""
    # create tagger objects
    logging.getLogger(INFO_LOGGER).info(f"Starting task 'create_tagger_objects' for TaggerGroup with ID: {tagger_group_id}!")

    taggers_to_create = []
    for i, tag in enumerate(tags):
        tagger_data = tagger_serializer.copy()
        tagger_data.update({"query": json.dumps(tag_queries[i])})
        tagger_data.update({"description": tag})
        tagger_data.update({"fields": json.dumps(tagger_data["fields"])})
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


@task(name="start_tagger_task", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def start_tagger_task(tagger_id: int):
    tagger = Tagger.objects.get(pk=tagger_id)
    task_object = tagger.task
    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step('starting tagging')
    show_progress.update_view(0)
    return tagger_id


@task(name="train_tagger_task", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def train_tagger_task(tagger_id: int):
    logging.getLogger(INFO_LOGGER).info(f"Starting task 'train_tagger' for tagger with ID: {tagger_id}!")
    tagger_object = Tagger.objects.get(id=tagger_id)
    task_object = tagger_object.task

    try:
        # create progress object
        show_progress = ShowProgress(task_object, multiplier=1)
        show_progress.update_step('scrolling positives')
        show_progress.update_view(0)

        # retrieve indices & field data
        indices = get_indices_from_object(tagger_object)
        field_data = json.loads(tagger_object.fields)
        # split stop words by space or newline and remove empties
        stop_words = re.split(" |\n|\r\n", tagger_object.stop_words)
        stop_words = [stop_word for stop_word in stop_words if stop_word]
        # load embedding if any
        if tagger_object.embedding:
            embedding = W2VEmbedding()
            embedding.load_django(tagger_object.embedding)
        else:
            embedding = None
        # create Datasample object for retrieving positive and negative sample
        data_sample = DataSample(
            tagger_object,
            indices=indices,
            field_data=field_data,
            show_progress=show_progress,
            #text_processor=text_processor
        )

        # update status to training
        show_progress.update_step("training")
        show_progress.update_view(0)
        # train model
        tagger = TextTagger(
            embedding=embedding,
            custom_stop_words=stop_words,
            classifier=tagger_object.classifier,
            vectorizer=tagger_object.vectorizer)
        tagger.train(
            data_sample.data["true"],
            data_sample.data["false"],
            field_list=json.loads(tagger_object.fields)
        )

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise e


@task(name="save_tagger_results", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def save_tagger_results(result_data: dict):
    try:

        tagger_id = result_data['id']
        tagger_object = Tagger.objects.get(pk=tagger_id)
        logging.getLogger(INFO_LOGGER).info(f"Starting task results for tagger with ID: {tagger_id}!")
        task_object = tagger_object.task
        show_progress = ShowProgress(task_object, multiplier=1)
        # update status to saving
        show_progress.update_step("saving")
        show_progress.update_view(0)
        # save tagger to disk
        tagger_path = tagger_object.generate_name("tagger")
        tagger.save(tagger_path)
        # set info about the model
        tagger_object.model.name = tagger_path
        tagger_object.precision = float(tagger.statistics["precision"])
        tagger_object.recall = float(tagger.statistics["recall"])
        tagger_object.f1_score = float(tagger.statistics["f1_score"])
        tagger_object.num_features = tagger.statistics["num_features"]
        tagger_object.num_positives = tagger.statistics["num_positives"]
        tagger_object.num_negatives = tagger.statistics["num_negatives"]
        tagger_object.model_size = round(float(os.path.getsize(tagger_path)) / 1000000, 1)  # bytes to mb
        tagger_object.plot.save(f"{secrets.token_hex(15)}.png", create_tagger_plot(tagger.statistics))
        tagger_object.save()
        # declare the job done
        task_object.complete()

    except Exception as e:
        logging.getLogger(ERROR_LOGGER).exception(e)
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise e


@task(name="apply_tagger", base=BaseTask)
def apply_tagger(tagger_id, text, input_type='text', lemmatize=False, feedback=None):
    """Task for applying tagger to text."""
    logging.getLogger(INFO_LOGGER).info(f"Starting task 'apply_tagger' for tagger with ID: {tagger_id} with params (input_type : {input_type}, lemmatize: {lemmatize}, feedback: {feedback})!")

    # get tagger object
    tagger_object = Tagger.objects.get(pk=tagger_id)

    # create text processor object for tagger
    stop_words = tagger_object.stop_words.split(' ')
    # load embedding
    if tagger_object.embedding:
        embedding = W2VEmbedding()
        embedding.load_django(tagger_object.embedding)
    else:
        embedding = False
    # load tagger
    tagger = TextTagger(embedding=embedding, mlp=lemmatizer, custom_stop_words=stop_words)
    tagger_loaded = tagger.load_django(tagger_object)
    # check if tagger gets loaded
    if not tagger_loaded:
        return None
    # check input type
    if input_type == 'doc':
        logging.getLogger(INFO_LOGGER).info(f"Tagging document with content: {text}!")
        tagger_result = tagger.tag_doc(text)
    else:
        logging.getLogger(INFO_LOGGER).info(f"Tagging text with content: {text}!")
        tagger_result = tagger.tag_text(text)
    # set bool result
    result = bool(tagger_result['prediction'])
    # create output dict
    prediction = {
        'tag': tagger.description,
        'probability': tagger_result['probability'],
        'tagger_id': tagger_id,
        'result': result
    }
    # add feedback if asked
    if feedback:
        logging.getLogger(INFO_LOGGER).info(f"Adding feedback for Tagger id: {tagger_object.pk}")
        project_pk = tagger_object.project.pk
        feedback_object = Feedback(project_pk, model_object=tagger_object)
        processed_text = text_processor.process(text)[0]
        feedback_id = feedback_object.store(processed_text, decision)
        feedback_url = f'/projects/{project_pk}/taggers/{tagger_object.pk}/feedback/'
        prediction['feedback'] = {'id': feedback_id, 'url': feedback_url}

    logging.getLogger(INFO_LOGGER).info(f"Completed task 'apply_tagger' for tagger with ID: {tagger_id}!")
    return prediction
