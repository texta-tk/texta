from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'start_training_job$', views.start_training_job, name='start_training_job'),
    url(r'delete_model$', views.delete_model, name='delete_model'),
    # API calls
    url(r'api/models$', views.api_list_models, name='api_list_models'),
    url(r'api/jobs', views.api_jobs, name='api_jobs'),
    url(r'api/classify$', views.api_classify, name='api_classify'),
    url(r'api/status$', views.api_job_status, name='api_job_status'),
]
