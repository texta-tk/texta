import json
import os
import secrets
from celery.decorators import task


from texta_tools.text_processor import TextProcessor

from texta_tools.mlp_analyzer import get_mlp_analyzer

from toolkit.core.task.models import Task
from toolkit.bert_tagger.models import BertTagger as BertTaggerObject
from toolkit.tools.show_progress import ShowProgress
from toolkit.base_tasks import TransactionAwareTask
from toolkit.elastic.data_sample import DataSample
from toolkit.tools.plots import create_tagger_plot
from toolkit.settings import RELATIVE_MODELS_PATH, CELERY_LONG_TERM_TASK_QUEUE
from toolkit.helper_functions import get_core_setting, get_indices_from_object
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

        tagger = BertTagger()
        # train tagger and get result statistics

        report = tagger.train(
            data_sample.data,
            n_epochs = tagger_object.num_epochs,
            max_length = tagger_object.max_length,
            batch_size = tagger_object.batch_size,
            lr = tagger_object.learning_rate,
            eps = tagger_object.eps,
            split_ratio = tagger_object.split_ratio,
            bert_model = tagger_object.bert_model

        )
        model_type = tagger_object.bert_model
        # save tagger to disk
        tagger_path = os.path.join(RELATIVE_MODELS_PATH, model_type, f'{model_type}_{tagger_id}_{secrets.token_hex(10)}')
        tagger.save(tagger_path)
        # set tagger location
        tagger_object.model.name = tagger_path
        # save tagger plot
        report_dict = report.to_dict()

        # TODO: display losses and scores per epoch!

        #tagger_object.plot.save(f'{secrets.token_hex(15)}.png', create_tagger_plot(report_dict), save=False)
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
        # save tagger object
        tagger_object.save()
        # declare the job done
        task_object.complete()
        return True


    except Exception as e:
        task_object.add_error(str(e))
        task_object.update_status(Task.STATUS_FAILED)
        raise
