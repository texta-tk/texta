from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'start_training_job$', views.start_training_job, name='start_training_job'),
    url(r'delete_model$', views.delete_model, name='delete_model'),
    url(r'test_model$', views.test_model, name='test_model'),
]
