import io
import json
import os
import pathlib
import secrets
import tempfile
import zipfile

from django.contrib.auth.models import User
from django.core import serializers
from django.db import models
from django.dispatch import receiver
from django.http import HttpResponse

from toolkit.constants import MAX_DESC_LEN
from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.embedding.models import Embedding
from . import choices
from toolkit.multiselectfield import PatchedMultiSelectField as MultiSelectField

# Create your models here.
from ..settings import MODELS_DIR


class Neurotagger(models.Model):
    MODEL_TYPE = 'neurotagger'
    MODEL_JSON_NAME = "model.json"

    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    indices = MultiSelectField(default=None)
    fields = models.TextField(default=json.dumps([]))
    fact_name = models.CharField(max_length=MAX_DESC_LEN, blank=True, help_text="Fact name from which to get value and generate classes/queries from")
    fact_values = models.TextField(blank=True, help_text="Fact values/class names that come from the given fact name")
    queries = models.TextField(default=json.dumps([]), help_text="Queries that will be generated from the given fact name")
    model_architecture = models.CharField(choices=choices.model_arch_choices, max_length=10, help_text="Neural network model architecture")
    seq_len = models.IntegerField(default=choices.DEFAULT_SEQ_LEN, help_text="Sequence length every input document will be cropped to, in order to save gpu memory and training speed")
    vocab_size = models.IntegerField(default=choices.DEFAULT_VOCAB_SIZE, help_text="Number of words that will be used in the vocabulary of the model")
    num_epochs = models.IntegerField(default=choices.DEFAULT_NUM_EPOCHS, help_text="Number of training passes through the data")
    validation_split = models.FloatField(default=choices.DEFAULT_VALIDATION_SPLIT, help_text="Percentage of data that will be used for validating instead of training")
    negative_multiplier = models.FloatField(default=choices.DEFAULT_NEGATIVE_MULTIPLIER, blank=True)
    score_threshold = models.FloatField(default=choices.DEFAULT_SCORE_THRESHOLD, blank=True)
    maximum_sample_size = models.IntegerField(default=choices.DEFAULT_MAX_SAMPLE_SIZE, blank=True)
    min_fact_doc_count = models.IntegerField(default=choices.DEFAULT_MIN_FACT_DOC_COUNT, blank=True, help_text="Number of minimum documents that a fact value needs to have before its used as a class")
    max_fact_doc_count = models.IntegerField(blank=True, null=True, help_text="Number of maximum documents that when a fact has, it will not be used as a class")
    embedding = models.ForeignKey(Embedding, on_delete=models.SET_NULL, null=True, default=None)

    # RESULTS
    validation_accuracy = models.FloatField(default=None, null=True)
    training_accuracy = models.FloatField(default=None, null=True)
    training_loss = models.FloatField(default=None, null=True)
    validation_loss = models.FloatField(default=None, null=True)
    classification_report = models.TextField(blank=True)

    # File-system resources
    model = models.FileField(null=True, verbose_name='', default=None, max_length=300)
    tokenizer_model = models.FileField(null=True, verbose_name='', default=None, max_length=300)
    tokenizer_vocab = models.FileField(null=True, verbose_name='', default=None, max_length=300)
    plot = models.FileField(upload_to='data/media', null=True, verbose_name='', max_length=300)

    # For extra info, such as the classification report, confusion matrix, model json, etc
    result_json = models.TextField(blank=True)

    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)


    def to_json(self) -> dict:
        serialized = serializers.serialize('json', [self])
        json_obj = json.loads(serialized)[0]["fields"]
        del json_obj["project"]
        del json_obj["author"]
        del json_obj["task"]
        return json_obj


    def export_resources(self) -> HttpResponse:
        with tempfile.SpooledTemporaryFile(encoding="utf8") as tmp:
            with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as archive:
                # write model object to zip as json
                model_json = self.to_json()
                model_json = json.dumps(model_json).encode("utf8")
                archive.writestr(self.MODEL_JSON_NAME, model_json)

                for file_path in self.get_resource_paths().values():
                    path = pathlib.Path(file_path)
                    archive.write(file_path, arcname=str(path.name))

            tmp.seek(0)
            return tmp.read()


    @staticmethod
    def import_resources(zip_file, request, pk) -> int:
        with zipfile.ZipFile(zip_file, 'r') as archive:
            json_string = archive.read(Neurotagger.MODEL_JSON_NAME).decode()
            model_json = json.loads(json_string)
            new_model = Neurotagger(**model_json)

            # Create a task object to fill the new model object with.
            # Pull the user and project into which it's imported from the web request.
            new_model.task = Task.objects.create(neurotagger=new_model, status=Task.STATUS_COMPLETED)
            new_model.author = User.objects.get(id=request.user.id)
            new_model.project = Project.objects.get(id=pk)
            new_model.save()  # Save the intermediate results.

            # Get all the informational segments from the name, later used in changing the id
            # to avoid any collisions just in case.
            new_neurotagger_name = new_model.generate_name("neurotagger")
            new_tokenizer_name = new_model.generate_name("neurotagger_tokenizer")

            with open(new_neurotagger_name, "wb") as fp:
                path = pathlib.Path(model_json["model"]).name
                fp.write(archive.read(path))
                new_model.model.name = new_neurotagger_name

            tokenizer_model_path = new_tokenizer_name + ".model"
            with open(tokenizer_model_path, "wb") as fp:
                path = pathlib.Path(model_json["tokenizer_model"]).name
                fp.write(archive.read(path))
                new_model.tokenizer_model.name = tokenizer_model_path

            tokenizer_vocab_path = new_tokenizer_name + ".vocab"
            with open(tokenizer_vocab_path, "wb") as fp:
                path = pathlib.Path(model_json["tokenizer_vocab"]).name
                fp.write(archive.read(path))
                new_model.tokenizer_vocab.name = tokenizer_vocab_path

            plot_name = pathlib.Path(model_json["plot"])
            path = plot_name.name
            new_model.plot.save(f'{secrets.token_hex(15)}.png', io.BytesIO(archive.read(path)))

            new_model.save()
            return new_model.id


    def get_resource_paths(self):
        """
        Return the full paths of every resource used by this model that lives
        on the filesystem.
        """
        return {
            "model": self.model.path,
            "plot": self.plot.path,
            "tokenizer_model": self.tokenizer_model.path,
            "tokenizer_vocab": self.tokenizer_vocab.path
        }


    def __str__(self):
        return '{0} - {1}'.format(self.pk, self.description)


    def generate_name(self, name="neurotagger"):
        filename = f'{name}_{self.pk}_{secrets.token_hex(10)}'
        filepath = pathlib.Path(MODELS_DIR) / "neurotagger" / filename
        return str(filepath)


    def train(self):
        new_task = Task.objects.create(neurotagger=self, status='created')
        self.task = new_task
        self.save()

        # FOR ASYNC SCROLLING WITH CELERY CHORD, SEE ISSUE https://git.texta.ee/texta/texta-rest/issues/66
        # Due to Neurotagger using chord, it has separate logic for calling out celery task and handling tests
        # if not 'test' in sys.argv:
        #     neurotagger_train_handler.apply_async(args=(instance.pk,))
        # else:
        #     neurotagger_train_handler(instance.pk, testing=True).apply()

        # TEMPORARILY SCROLL SYNCHRONOUSLY INSTEAD
        from toolkit.neurotagger.tasks import neurotagger_train_handler
        from toolkit.helper_functions import apply_celery_task
        apply_celery_task(neurotagger_train_handler, self.pk)


@receiver(models.signals.post_delete, sender=Neurotagger)
def auto_delete_file_on_delete(sender, instance: Neurotagger, **kwargs):
    """
    Delete resources on the file-system upon neurotagger deletion.
    Triggered on individual model object and queryset Neurotagger deletion.
    """
    if instance.plot:
        if os.path.isfile(instance.plot.path):
            os.remove(instance.plot.path)

    if instance.model:
        if os.path.isfile(instance.model.path):
            os.remove(instance.model.path)

    if instance.tokenizer_model:
        if os.path.isfile(instance.tokenizer_model.path):
            os.remove(instance.tokenizer_model.path)

    if instance.tokenizer_vocab:
        if os.path.isfile(instance.tokenizer_vocab.path):
            os.remove(instance.tokenizer_vocab.path)
