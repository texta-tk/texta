from django.conf.urls import url

from ontology_viewer.views import *


urlpatterns = [
    url(r'^$', index, name='index'),
    url(r'get_concepts$',get_concepts, name='get_concepts'),
    url(r'get_concept_terms$',get_concept_terms, name='get_concept_terms'),
    url(r'delete_concept',delete_concept,name="delete_concept"),
    url(r'delete_term',delete_term,name='delete_term'),
]
