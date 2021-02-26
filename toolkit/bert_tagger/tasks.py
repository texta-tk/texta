import json
import os
import secrets
import logging
from celery.decorators import task
from django.db import connections

from toolkit.core.task.models import Task
from toolkit.bert_tagger.models import BertTagger as BertTaggerObject
from toolkit.tools.show_progress import ShowProgress
from toolkit.base_tasks import TransactionAwareTask
from toolkit.elastic.tools.data_sample import DataSample
from toolkit.tools.plots import create_tagger_plot
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, BERT_PRETRAINED_MODEL_DIRECTORY, BERT_FINETUNED_MODEL_DIRECTORY, BERT_CACHE_DIR, INFO_LOGGER
from toolkit.helper_functions import get_core_setting, get_indices_from_object
from toolkit.bert_tagger import choices

from texta_bert_tagger.tagger import BertTagger


@task(name="train_bert_tagger", base=TransactionAwareTask, queue=CELERY_LONG_TERM_TASK_QUEUE)
def train_bert_tagger(tagger_id, testing=False):
    try:
        # retrieve neurotagger & task objects
        tagger_object = BertTaggerObject.objects.get(pk=tagger_id)
        task_object = tagger_object.task
        #model_type = BertTaggerObject.MODEL_TYPE
        show_progress = ShowProgress(task_object, multiplier=1)
        # get fields & indices
        fields = json.loads(tagger_object.fields)
        indices = get_indices_from_object(tagger_object)

        bert_model = tagger_object.bert_model

        # create Datasample object for retrieving positive and negative sample
        data_sample = DataSample(
            tagger_object,
            indices,
            fields,
            show_progress=show_progress,
            join_fields=True
        )
        show_progress.update_step('training')
        show_progress.update_view(0.0)

        # select sklearn average function based on the number of classes
        if data_sample.is_binary:
            sklearn_avg_function = choices.DEFAULT_SKLEARN_AVG_BINARY
        else:
            sklearn_avg_function = choices.DEFAULT_SKLEARN_AVG_MULTICLASS


        # NB! saving pretrained models must be disabled!
        tagger = BertTagger(
            allow_standard_output = choices.DEFAULT_ALLOW_STANDARD_OUTPUT,
            autoadjust_batch_size = choices.DEFAULT_AUTOADJUST_BATCH_SIZE,
            sklearn_avg_function = sklearn_avg_function,
            use_gpu = choices.DEFAULT_USE_GPU,
            save_pretrained = False,
            pretrained_models_dir = "",
            logger = logging.getLogger(INFO_LOGGER),
            cache_dir = BERT_CACHE_DIR
        )

        # train tagger and get result statistics
        report = tagger.train(
            data_sample.data,
            n_epochs = tagger_object.num_epochs,
            max_length = tagger_object.max_length,
            batch_size = tagger_object.batch_size,
            lr = tagger_object.learning_rate,
            eps = tagger_object.eps,
            split_ratio = tagger_object.split_ratio,
            bert_model = bert_model
        )
        # close all db connections
        for conn in connections.all():
            conn.close_if_unusable_or_obsolete()

        # save tagger to disc
        tagger_path = os.path.join(BERT_FINETUNED_MODEL_DIRECTORY, f'{tagger_object.MODEL_TYPE}_{tagger_id}_{secrets.token_hex(10)}')
        tagger.save(tagger_path)

        # set tagger location
        tagger_object.model.name = tagger_path

        report_dict = report.to_dict()

        # save tagger plot
        tagger_object.plot.save(f'{secrets.token_hex(15)}.png', create_tagger_plot(report_dict), save=False)
        # save label index
        tagger_object.label_index = json.dumps(tagger.config.label_reverse_index)
        # stats to model object
        tagger_object.f1_score = report.f1_score
        tagger_object.precision = report.precision
        tagger_object.recall = report.recall
        tagger_object.accuracy = report.accuracy
        tagger_object.training_loss = report.training_loss
        tagger_object.validation_loss = report.validation_loss
        tagger_object.epoch_reports = json.dumps([a.to_dict() for a in tagger.epoch_reports])
        tagger_object.num_examples = json.dumps({k: len(v) for k, v in list(data_sample.data.items())})
        tagger_object.adjusted_batch_size = tagger.config.batch_size
        tagger_object.confusion_matrix = json.dumps(report.confusion.tolist())
        # save tagger object
        tagger_object.save()
        # declare the job done
        task_object.complete()
        return True


    except Exception as e:
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise
