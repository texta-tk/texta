from django.db import models
from django.contrib.auth.models import User
from ..permission_admin.models import Dataset
from django.utils import timezone

class GrammarComponent(models.Model):
    name = models.CharField(max_length=256)
    type = models.CharField(max_length=64)
    content = models.CharField(max_length=512,null=True, blank=True)
    layer = models.CharField(max_length=64, null=True, blank=True)
    join_by = models.CharField(max_length=32, null=True, blank=True)
    sub_components = models.ManyToManyField('grammar_builder.GrammarComponent')
    author = models.ForeignKey(User, related_name='grammar_components')
    
    def __str__(self):
        return "{\tName: %s\n\tType: %s\n\tContent: %s\n\tLayer: %s\n\tJoin-by: %s\n}"%(self.name, self.type, self.content, self.layer, self.join_by)


# Maps grammar tool's session data (search_id, inclusive_grammar, exclusive_grammar) and pagination step to
# specific cursor location ('from') in Elastic Search.
class GrammarPageMapping(models.Model):
    search_id = models.IntegerField()
    inclusive_grammar = models.IntegerField()
    exclusive_grammar = models.IntegerField()
    polarity = models.CharField(max_length=8)
    page = models.IntegerField()
    elastic_start = models.IntegerField()
    elastic_end = models.IntegerField()
    author = models.ForeignKey(User)
    
class Grammar(models.Model):
    name = models.CharField(max_length=64)
    json = models.CharField(max_length=2048)
    last_modified = models.DateTimeField()
    author = models.ForeignKey(User)
    dataset = models.ForeignKey(Dataset)

    def save(self, *args, **kwargs):
        """From http://stackoverflow.com/questions/1737017/django-auto-now-and-auto-now-add - update last_modified on save """
        self.last_modified = timezone.now()
        return super(Grammar, self).save(*args, **kwargs)