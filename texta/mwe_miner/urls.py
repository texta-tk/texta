from django.conf.urls import url

from ..mwe_miner.views import *


urlpatterns = [
    url(r'^$',index, name='index'),
    url(r'start_mapping_job$',start_mapping_job,name='start_mapping_job'),
    url(r'results$',results,name='results'),
    url(r'approve$',approve,name='approve'),
    url(r'delete_result$',delete_result,name='delete_result'),
    url(r'commit$',commit,name="commit")
]
