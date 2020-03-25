import json
import logging
import os
import re
import secrets

from texta_tagger.tagger import Tagger as TextTagger
from texta_tools.text_processor import TextProcessor
from texta_tools.mlp_analyzer import get_mlp_analyzer
from texta_tools.embedding import Phraser, W2VEmbedding

from celery.decorators import task
from toolkit.base_task import BaseTask
from toolkit.core.task.models import Task
from toolkit.elastic.data_sample import DataSample
from toolkit.elastic.feedback import Feedback
from toolkit.helper_functions import get_indices_from_object, get_core_setting
from toolkit.settings import ERROR_LOGGER
from toolkit.tagger.models import Tagger, TaggerGroup
from toolkit.tagger.plots import create_tagger_plot
from toolkit.tools.show_progress import ShowProgress


def create_tagger_batch(tagger_group_id, taggers_to_create):
    """Creates Tagger objects from list of tagger data and saves into tagger group object."""
    # retrieve Tagger Group object
    tagger_group_object = TaggerGroup.objects.get(pk=tagger_group_id)
    # iterate through batch
    for tagger_data in taggers_to_create:
        created_tagger = Tagger.objects.create(
            **tagger_data,
            author=tagger_group_object.author,
            project=tagger_group_object.project
        )
        # add and save
        tagger_group_object.taggers.add(created_tagger)
        tagger_group_object.save()
        # train
        created_tagger.train()


def get_lemmatizer(lemmatize):
    lemmatizer = None
    if lemmatize:
        mlp_url = get_core_setting("TEXTA_MLP_URL")
        mlp_major_version = get_core_setting("TEXTA_MLP_MAJOR_VERSION")
        lemmatizer = get_mlp_analyzer(mlp_host=mlp_url, mlp_major_version=mlp_major_version)
    return lemmatizer


@task(name="create_tagger_objects", base=BaseTask)
def create_tagger_objects(tagger_group_id, tagger_serializer, tags, tag_queries, batch_size=100):
    """Task for creating Tagger objects inside Tagger Group to prevent database timeouts."""
    # create tagger objects
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
    return True


@task(name="train_tagger", base=BaseTask)
def train_tagger(tagger_id):
    """Task for training Text Tagger."""
    # retrieve tagger & task objects
    tagger_object = Tagger.objects.get(pk=tagger_id)
    task_object = tagger_object.task
    # create progress object
    show_progress = ShowProgress(task_object, multiplier=1)
    show_progress.update_step("scrolling positives")
    show_progress.update_view(0)

    try:
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
            show_progress=show_progress,
            #text_processor=text_processor
        )
        # get lemmatizer if needed
        lemmatizer = get_lemmatizer(tagger_object.lemmatize)
        # update status to training
        show_progress.update_step("training")
        show_progress.update_view(0)
        # train model
        tagger = TextTagger(
            embedding=embedding,
            mlp=lemmatizer,
            custom_stop_words=stop_words,
            classifier=tagger_object.classifier,
            vectorizer=tagger_object.vectorizer)
        tagger.train(
            data_sample.data["true"],
            data_sample.data["false"],
            field_list=json.loads(tagger_object.fields)
        )
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
        show_progress.update_step("")
        show_progress.update_view(100.0)
        task_object.update_status(Task.STATUS_COMPLETED, set_time_completed=True)
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
    # get tagger object
    tagger_object = Tagger.objects.get(pk=tagger_id)
    # get lemmatizer if needed
    lemmatizer = get_lemmatizer(lemmatize)
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
    if input_type == "doc":
        tagger_result = tagger.tag_doc(text)
    else:
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
        project_pk = tagger_object.project.pk
        feedback_object = Feedback(project_pk, model_object=tagger_object)
        feedback_id = feedback_object.store(text, result)
        feedback_url = f'/projects/{project_pk}/taggers/{tagger_object.pk}/feedback/'
        prediction['feedback'] = {'id': feedback_id, 'url': feedback_url}
    return prediction
