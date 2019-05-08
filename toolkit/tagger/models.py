import json
from django.db.models import signals
from django.dispatch import receiver
from django.db import models
from multiselectfield import MultiSelectField

from toolkit.embedding.choices import get_field_choices
from toolkit.elastic.searcher import ElasticSearcher
from toolkit.core.models import Project, Task, UserProfile
from toolkit.embedding.models import Embedding

MAX_STR_LEN = 100


class Tagger(models.Model):
    id = models.AutoField(primary_key=True)
    description = models.CharField(max_length=MAX_STR_LEN)
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(UserProfile, on_delete=models.CASCADE)
    query = models.TextField(default=json.dumps(ElasticSearcher().query))
    fields = MultiSelectField(choices=get_field_choices(), default=None)
    embedding = models.ForeignKey(Embedding, on_delete=models.SET_NULL, null=True, default=None)

    vectorizer = models.IntegerField()
    classifier = models.IntegerField()
    negative_multiplier = models.FloatField(default=1.0)
    maximum_sample_size = models.IntegerField(default=10000)
    score_threshold = models.FloatField(default=0.0)

    location = models.TextField()
    statistics = models.TextField()
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)

    def __str__(self):
        return self.description

    @classmethod
    def train_tagger_model(cls, sender, instance, created, **kwargs):
        if created:
            new_task = Task.objects.create(tagger=instance, status='created')
            instance.task = new_task
            instance.save()
            from toolkit.tagger.tasks import train_tagger
            train_tagger.apply_async(args=(instance.pk,))


signals.post_save.connect(Tagger.train_tagger_model, sender=Tagger)
