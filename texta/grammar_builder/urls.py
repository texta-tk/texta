from django.conf.urls import url

from ..grammar_builder.views import *


urlpatterns = [
    url(r'^$', index, name='index'),
    url(r'get_table_data', get_table_data, name='get_table_data'),
    url(r'get_table', get_table, name='get_table'),
]
