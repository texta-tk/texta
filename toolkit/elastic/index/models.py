from django.db import models


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
