import tempfile
import zipfile
import json

from django.contrib.auth.models import User
from django.db import models, transaction
from django.core import serializers

from toolkit.core.project.models import Project
from toolkit.constants import MAX_DESC_LEN


class Anonymizer(models.Model):
    MODEL_TYPE = "anonymizer"
    MODEL_JSON_NAME = "model.json"

    description = models.CharField(max_length=MAX_DESC_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)

    replace_misspelled_names = models.BooleanField(default=True)
    replace_single_last_names = models.BooleanField(default=True)
    replace_single_first_names = models.BooleanField(default=True)
    misspelling_threshold = models.FloatField(default=0.9)
    mimic_casing = models.BooleanField(default=True)
    auto_adjust_threshold = models.BooleanField(default=False)

    def __str__(self):
        return self.description

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
                json_string = archive.read(Anonymizer.MODEL_JSON_NAME).decode()
                model_json = json.loads(json_string)[0]["fields"]
                del model_json["project"]
                del model_json["author"]
                # create new object
                new_model = Anonymizer(**model_json)
                # update user & project
                new_model.author = User.objects.get(id=request.user.id)
                new_model.project = Project.objects.get(id=pk)
                new_model.save()
                return new_model.id
