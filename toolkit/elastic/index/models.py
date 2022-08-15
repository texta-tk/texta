from django.db import models


class Index(models.Model):
    """
    Do NOT in any circumstance sync model deletion and creation
    with ANY index operation towards Elasticsearch if your life is dear
    to you. There are several places in tests that have Index.objects.delete.all()...

    Keep it in the views...
    """
    name = models.CharField(max_length=255, unique=True)
    is_open = models.BooleanField(default=True)
    description = models.CharField(max_length=255, default="")
    added_by = models.CharField(max_length=255, default="")
    test = models.BooleanField(default=False)
    source = models.CharField(max_length=255, default="")
    client = models.CharField(max_length=255, default="")
    domain = models.CharField(max_length=255, default="")
    created_at = models.DateTimeField(null=True)


    def __str__(self):
        return self.name


    @staticmethod
    def check_and_create(indices: str):
        from texta_elastic.core import ElasticCore
        ec = ElasticCore()

        if isinstance(indices, list):
            indices = indices
        elif isinstance(indices, str):
            indices = indices.split(",")

        for index in indices:
            does_exist = ec.check_if_indices_exist([index])
            if does_exist:
                Index.objects.get_or_create(name=index)
            else:
                Index.objects.filter(name=index).delete()
