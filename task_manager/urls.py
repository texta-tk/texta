from django.conf.urls import url

from . import views
from . import api_v1


urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^start_task$', views.start_task, name='start_task'),
    url(r'^delete_task$', views.delete_task, name='delete_task'),
    url(r'download_model$', views.download_model, name='download_model'),

    # API
    url(r'^api/v1$', api_v1.api_info, name='api_info'),
    url(r'^api/v1/task_list$', api_v1.api_get_task_list, name='api_get_task_list'),
    url(r'^api/v1/task_status$', api_v1.api_get_task_status, name='api_get_task_status'),
    url(r'^api/v1/train_model$', api_v1.api_train_model, name='api_train_model'),
    url(r'^api/v1/train_tagger$', api_v1.api_train_tagger, name='api_train_tagger'),
    url(r'^api/v1/apply$', api_v1.api_apply, name='api_apply'),

    url(r'^api/v1/dataset_list$', api_v1.api_dataset_list, name='api_dataset_list'),
    url(r'^api/v1/tag_list$', api_v1.api_tag_list, name='api_tag_list'),
    url(r'^api/v1/mass_train_tagger$', api_v1.api_mass_train_tagger, name='api_mass_train_tagger'),
]
