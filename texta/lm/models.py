from django.db import models
from django.contrib.auth.models import User

MAX_INT_LEN = 10
MAX_STR_LEN = 100


class Lexicon(models.Model):
    name = models.CharField(max_length=MAX_STR_LEN)
    description = models.CharField(max_length=MAX_STR_LEN)
    author = models.ForeignKey(User)

    def __str__(self):
        return self.name.encode('utf8')


class SuggestionSet(models.Model):
    lexicon = models.ForeignKey(Lexicon)
    method = models.CharField(max_length=MAX_STR_LEN)

    
class Word(models.Model):
    lexicon = models.ForeignKey(Lexicon)
    wrd = models.CharField(max_length=MAX_STR_LEN)
    suggestionset = models.ForeignKey(SuggestionSet, null=True)
   
    def __str__(self):
        return self.wrd
