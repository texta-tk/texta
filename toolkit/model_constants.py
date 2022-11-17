import io
import json
import logging
import pathlib
import uuid
from typing import List, Optional

import slugify
from django.conf import settings
from django.contrib.auth.models import User
from django.core.validators import MaxValueValidator, MinValueValidator
from django.db import models
from minio import Minio
from texta_elastic.searcher import EMPTY_QUERY

from toolkit.core.project.models import Project
from toolkit.core.task.models import Task
from toolkit.elastic.index.models import Index
from toolkit.helper_functions import get_minio_client, get_core_setting
from toolkit.serializer_constants import BULK_SIZE_HELPTEXT, DESCRIPTION_HELPTEXT, ES_TIMEOUT_HELPTEXT, INDICES_HELPTEXT
from toolkit.settings import DESCRIPTION_CHAR_LIMIT, ES_BULK_SIZE_MAX, ES_TIMEOUT_MAX

S3_ZIP_NAME = "model.zip"


class CommonModelMixin(models.Model):
    description = models.CharField(max_length=DESCRIPTION_CHAR_LIMIT, help_text=DESCRIPTION_HELPTEXT)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, null=True, on_delete=models.SET_NULL)
    tasks = models.ManyToManyField(Task)

    class Meta:
        abstract = True


class TaskModel(CommonModelMixin):
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    indices = models.ManyToManyField(Index, default=[], help_text=INDICES_HELPTEXT)
    fields = models.TextField(default=json.dumps([]))

    bulk_size = models.IntegerField(default=100, help_text=BULK_SIZE_HELPTEXT, validators=[MinValueValidator(1), MaxValueValidator(ES_BULK_SIZE_MAX)])
    es_timeout = models.IntegerField(default=10, help_text=ES_TIMEOUT_HELPTEXT, validators=[MinValueValidator(1), MaxValueValidator(ES_TIMEOUT_MAX)])

    class Meta:
        abstract = True

    def get_available_or_all_indices(self, indices: List[str] = None) -> List[str]:
        """
        Used in views where the user can select the indices they wish to use.
        Returns a list of index names from the ones that are in the project
        and in the indices parameter or all of the indices if it's None or empty.
        """
        if indices:
            indices = self.indices.filter(name__in=indices, is_open=True)
            if not indices:
                indices = self.project.indices.all()
        else:
            indices = self.indices.all()

        indices = [index.name for index in indices]
        indices = list(set(indices))  # Leave only unique names just in case.
        return indices

    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]

    def __str__(self):
        return '{0} - {1}'.format(self.pk, self.description)


class FavoriteModelMixin(models.Model):
    favorited_users = models.ManyToManyField(User, related_name="%(app_label)s_%(class)s_favorited_user")

    class Meta:
        abstract = True


class S3ModelMixin:

    @classmethod
    def download_from_s3(cls, minio_location: str, user_pk: int, project_pk: int, version_id: str = "") -> int:
        client = get_minio_client()
        kwargs = {"version_id": version_id} if version_id else {}
        bucket_name = get_core_setting("TEXTA_S3_BUCKET_NAME")
        response = client.get_object(bucket_name, minio_location, **kwargs)
        data = io.BytesIO(response.data)
        tagger_pk = cls.import_resources(data, user_pk, project_pk)
        response.close()
        return tagger_pk

    def upload_into_s3(self, minio_path: str, data: Optional[bytes] = None, filepath: Optional[str] = None):
        client = get_minio_client()
        metadata = self.to_json()  # Adding this breaks things for some reason.
        # Upload the model file directly.
        # TODO Remove the path generation from the upload function.
        response = self._push_object_into_s3(client, minio_path=minio_path, data=data, local_filepath=filepath)
        return response

    def _push_object_into_s3(self, client: Minio, minio_path: str, data: Optional[bytes] = None, local_filepath: Optional[str] = None):
        bucket_name = get_core_setting("TEXTA_S3_BUCKET_NAME")
        if local_filepath and data is None:
            response = client.fput_object(
                bucket_name=bucket_name,
                object_name=minio_path,
                file_path=str(local_filepath)
            )

        # Upload a passed collection of bytes.
        elif data and minio_path:
            data = io.BytesIO(data)
            size = data.getbuffer().nbytes
            response = client.put_object(
                bucket_name=bucket_name,
                object_name=minio_path,
                data=data,
                length=size
            )
        else:
            raise ValueError("Faulty input, neither a path to a local file or a binary with its MINIO path was supplied!")

        return response

    @staticmethod
    def check_for_s3_access(s3_for_instance: bool) -> bool:
        info_logger = logging.getLogger(settings.INFO_LOGGER)

        if get_core_setting("TEXTA_S3_ENABLED") is False:
            info_logger.info("[Tagger] Saving into S3 is disabled system wide!")
            return False

        # When user doesn't want the item to be uploaded.
        if s3_for_instance is False:
            info_logger.info("[Tagger] Saving into S3 is disabled tagger instance side!")
            return False

        try:
            client = get_minio_client()
            bucket_name = get_core_setting("TEXTA_S3_BUCKET_NAME")
            list(client.list_objects(bucket_name))
            return True
        except Exception as e:
            logging.getLogger(settings.ERROR_LOGGER).exception(e)
            return False

    def generate_s3_location(self, file_name: str = S3_ZIP_NAME, file_path: Optional[str] = None):
        """
        Generates the full path to the file you wish to access.
        :param file_path: Full filepath of the file without the filename.
        :param file_name: Stem/name of the file in question, includes the filename and extension.
        :return: Full path to be uploaded into the S3 instance.
        """
        if file_path:
            path = pathlib.Path(file_path)
            path = path / file_name if path.name != file_name else path
        else:
            project_slug = slugify.slugify(self.project.title)
            path = pathlib.Path(f"{project_slug}_{uuid.uuid4().hex}") / file_name
        return str(path)
