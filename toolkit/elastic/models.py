import json

from django.contrib.auth.models import User, User
from django.db import models
from django.db.models import signals

from toolkit.constants import MAX_DESC_LEN
from toolkit.core.task.models import Task, Task, Task
from toolkit.elastic.searcher import EMPTY_QUERY
from toolkit.elastic.choices import LABEL_DISTRIBUTION
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE


class Index(models.Model):
    """
    To NOT in any circumstance sync model deletion and creation
    with ANY index operation towards Elasticsearch if your life is dear
    to you. There are several places in tests that have Index.objects.delete.all()...

    Keep it in the views...
    """
    name = models.CharField(max_length=255, unique=True)
    is_open = models.BooleanField(default=True)


    def __str__(self):
        return self.name


class Reindexer(models.Model):
    from toolkit.core.project.models import Project

    description = models.CharField(max_length=MAX_DESC_LEN, default="")
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    scroll_size = models.IntegerField(default=500)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    indices = models.TextField(default=json.dumps([]))
    fields = models.TextField(default=json.dumps([]))
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)
    new_index = models.CharField(max_length=MAX_DESC_LEN, default="")
    random_size = models.IntegerField(default=0)
    field_type = models.TextField(default=json.dumps([]))
    add_facts_mapping = models.BooleanField(default=False)


    def __str__(self):
        return self.description


    @classmethod
    def create_reindexer_model(cls, sender, instance, created, **kwargs):
        if created:
            new_task = Task.objects.create(reindexer=instance, status='created')
            instance.task = new_task
            instance.save()

            from toolkit.elastic.tasks import reindex_task
            reindex_task.apply_async(args=(instance.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE)


signals.post_save.connect(Reindexer.create_reindexer_model, sender=Reindexer)

class IndexSplitter(models.Model):
    from toolkit.core.project.models import Project

    description = models.CharField(max_length=MAX_DESC_LEN, default="")
    project = models.ForeignKey(Project, on_delete=models.CASCADE)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
    scroll_size = models.IntegerField(default=500)
    query = models.TextField(default=json.dumps(EMPTY_QUERY))
    indices = models.ManyToManyField(Index)
    fields = models.TextField(default=json.dumps([]))
    task = models.OneToOneField(Task, on_delete=models.SET_NULL, null=True)

    train_index = models.CharField(max_length=MAX_DESC_LEN, default="")
    test_index = models.CharField(max_length=MAX_DESC_LEN, default="")
    fact = models.CharField(max_length=MAX_DESC_LEN, default="")
    str_val = models.CharField(max_length=MAX_DESC_LEN, default="")

    test_size = models.IntegerField(default=20)
    distribution = models.TextField(default=LABEL_DISTRIBUTION[0][0])
    custom_distribution = models.TextField(default=json.dumps({}))

    def get_indices(self):
        return [index.name for index in self.indices.filter(is_open=True)]

    def get_query(self):
        return json.loads(self.query)

    def get_custom_distribution(self):
        return json.loads(self.custom_distribution)

    def start_task(self):
        new_task = Task.objects.create(indexsplitter=self, status='created')
        self.task = new_task
        self.save()
        from toolkit.elastic.tasks import index_splitting_task
        index_splitting_task.apply_async(args=(self.pk,), queue=CELERY_LONG_TERM_TASK_QUEUE)