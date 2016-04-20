from django.conf.urls import url

from corpus_tool.views import *


urlpatterns = [
    url(r'^$', index, name='index'),
    url(r'search',search, name='search'),
    url(r'aggregate',aggregate, name='aggregate'),
    url(r'save',save, name='save'),
    url(r'delete',delete, name='delete'),
    url(r'autocomplete',autocomplete, name='autocomplete'),
    url(r'listing',get_saved_searches, name='get_saved_searches'),
    url(r'get_examples',get_examples, name='get_examples'),
    url(r'examples',get_examples_table, name='get_examples_table'),
    url(r'export',export_pages, name='export_pages'),
]
