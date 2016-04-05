from django.conf.urls import url

from lm.views import *


urlpatterns = [
    url(r'^$', index, name='index'),
    url(r'new$',newLexicon, name='newLexicon'),
    url(r'delete',deleteLexicon, name='deleteLexicon'),
    url(r'save$',saveLexicon, name='saveLexicon'),
    url(r'select',selectLexicon, name='selectLexicon'),
    url(r'query$',query, name='query'),
    url(r'reset_suggestions',reset_suggestions, name="reset_suggestions"),
]
