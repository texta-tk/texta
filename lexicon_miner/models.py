from django.db import models
from django.contrib.auth.models import User

MAX_INT_LEN = 10
MAX_STR_LEN = 100


class Lexicon(models.Model):
    id = models.AutoField(primary_key=True)
    name = models.CharField(max_length=MAX_STR_LEN)
    description = models.CharField(max_length=MAX_STR_LEN)
    author = models.ForeignKey(User,
    on_delete=models.CASCADE)

    def __str__(self):
        return self.name


class SuggestionSet(models.Model):
    id = models.AutoField(primary_key=True)
    lexicon = models.ForeignKey(Lexicon, on_delete=models.CASCADE)
    method = models.CharField(max_length=MAX_STR_LEN)

    
class Word(models.Model):
    id = models.AutoField(primary_key=True)
    lexicon = models.ForeignKey(Lexicon, on_delete=models.CASCADE)
    wrd = models.CharField(max_length=MAX_STR_LEN)
    suggestionset = models.ForeignKey(SuggestionSet,
    on_delete=models.CASCADE,
    null=True)
   
    def __str__(self):
        return self.wrd
