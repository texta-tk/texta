from django.db import models
from django.contrib.auth.models import User

MAX_INT_LEN = 10
MAX_STR_LEN = 100
   
class Term(models.Model):
    id = models.AutoField(primary_key=True)
    is_internal = models.BooleanField()
    term = models.CharField(max_length=MAX_STR_LEN)
    author = models.ForeignKey(User,on_delete=models.CASCADE,
related_name='term_author_relation_set')

    def __repr__(self):
        return self.term.encode('utf8')
    
class Concept(models.Model):
    id = models.AutoField(primary_key=True)
    descriptive_term = models.ForeignKey(Term, on_delete=models.CASCADE)

    semantic_type = models.CharField(max_length=MAX_STR_LEN)
    author = models.ForeignKey(User, on_delete=models.CASCADE)
   
class Reference(models.Model):
    id = models.AutoField(primary_key=True)
    concept = models.ForeignKey(Concept, on_delete=models.CASCADE)
    code_set = models.CharField(max_length=MAX_STR_LEN)
    code = models.CharField(max_length=MAX_STR_LEN)
    
class TermConcept(models.Model):
    id = models.AutoField(primary_key=True)
    term = models.ForeignKey(Term, on_delete=models.CASCADE)
    concept = models.ForeignKey(Concept, on_delete=models.CASCADE)