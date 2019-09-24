from multiselectfield import MultiSelectField
from toolkit.constants import MAX_DESC_LEN
from toolkit.elastic.core import ElasticCore
from django.db import models
import json

# TODO, get only project_indices into our indices field.
# TODO, implement how to GET the necessary info, probably with extra_action
# TODO, implement indices as objects

class Reindexer(models.Model):
    description = models.CharField(max_length=MAX_DESC_LEN)
    indices = MultiSelectField(default=None)
    fields = models.TextField(default=json.dumps([]))

    def __str__(self):
        return self.description

    def get_elastic_fields(self, path_list=False):
        """
        Method for retrieving all valid Elasticsearch fields for a given project.
        """
        if not self.indices:
            return []
        field_data = ElasticCore().get_fields(indices=self.indices)
        if path_list:
            field_data = [field["path"] for field in field_data]
        return field_data


#     @classmethod
#     def create_reindexer_model(cls, sender, instance, created, **kwargs):
#         if created:
#             new_task = Task.objects.create(embedding=instance, status='created')
#             instance.task = new_task
#             instance.save()
#             from toolkit.embedding.tasks import train_embedding

#             apply_celery_task(train_embedding, instance.pk)


# signals.post_save.connect(Embedding.train_embedding_model, sender=Reindexer)
