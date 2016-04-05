from django.conf.urls import url

from model_manager.views import *


urlpatterns = [
    url(r'^$',index, name='index'),
    url(r'start_training_job$',start_training_job,name='start_training_job'),
    url(r'delete_model$',delete_model,name='delete_model'),
]
