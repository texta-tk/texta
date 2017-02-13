from django.db import models
from django.contrib.auth.models import User

MAX_INT_LEN = 10
MAX_STR_LEN = 100
   
class Term(models.Model):
    is_internal = models.BooleanField()
    term = models.CharField(max_length=MAX_STR_LEN)
    author = models.ForeignKey(User,related_name='term_author_relation_set')

    def __repr__(self):
        return self.term.encode('utf8')
    
class Concept(models.Model):
    descriptive_term = models.ForeignKey(Term)
    semantic_type = models.CharField(max_length=MAX_STR_LEN)
    author = models.ForeignKey(User)
   
class Reference(models.Model):
    concept = models.ForeignKey(Concept)
    code_set = models.CharField(max_length=MAX_STR_LEN)
    code = models.CharField(max_length=MAX_STR_LEN)
    
class TermConcept(models.Model):
    term = models.ForeignKey(Term)
    concept = models.ForeignKey(Concept)