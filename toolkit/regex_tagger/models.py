import tempfile
import zipfile
import json

from django.contrib.auth.models import User
from django.db import models, transaction
from django.core import serializers

from toolkit.core.project.models import Project
from toolkit.constants import MAX_DESC_LEN
from .choices import OPERATOR_CHOICES, MATCH_TYPE_CHOICES


class RegexTagger(models.Model):
    MODEL_TYPE = "regex_tagger"
    MODEL_JSON_NAME = "model.json"

    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)

    lexicon = models.TextField(default='')
    counter_lexicon = models.TextField(default='')
    operator = models.CharField(max_length=25, default=OPERATOR_CHOICES[0][0])
    match_type = models.CharField(max_length=25, default=MATCH_TYPE_CHOICES[0][0])
    required_words = models.FloatField(default=0.0)
    phrase_slop = models.IntegerField(default=0)
    counter_slop = models.IntegerField(default=0)
    return_fuzzy_match = models.BooleanField(default=True)


    def export_resources(self):
        with tempfile.SpooledTemporaryFile(encoding="utf8") as tmp:
            with zipfile.ZipFile(tmp, 'w', zipfile.ZIP_DEFLATED) as archive:
                # Write model object to zip as json
                model_json = serializers.serialize("json", [self]).encode("utf8")
                archive.writestr(self.MODEL_JSON_NAME, model_json)
            tmp.seek(0)
            return tmp.read()


    @staticmethod
    def import_resources(zip_file, request, pk) -> int:
        with transaction.atomic():
            with zipfile.ZipFile(zip_file, "r") as archive:
                json_string = archive.read(RegexTagger.MODEL_JSON_NAME).decode()
                model_json = json.loads(json_string)[0]["fields"]
                del model_json["project"]
                del model_json["author"]
                # create new object
                new_model = RegexTagger(**model_json)
                # update user & project
                new_model.author = User.objects.get(id=request.user.id)
                new_model.project = Project.objects.get(id=pk)
                new_model.save()
                return new_model.id
