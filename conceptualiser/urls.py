from django.conf.urls import url

from conceptualiser.views import *


urlpatterns = [
    url(r'^$', index, name='index'),
    url(r'load$',load_terms, name='load_terms'),
    url(r'get_lexicons$',get_lexicons, name='get_lexicons'),
    url(r'save$',save_concepts, name='save'),
]
