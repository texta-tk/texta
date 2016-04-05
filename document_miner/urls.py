from django.conf.urls import url

from document_miner.views import *


urlpatterns = [
    url(r'^$', index, name='index'),
    url(r'query$', query, name='query'),
]
