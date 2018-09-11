from django.conf.urls import url

from task_manager import views


urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^start_task$', views.start_task, name='start_task'),
    url(r'^delete_task$', views.delete_task, name='delete_task'),
    url(r'download_model$', views.download_model, name='download_model'),

    # API
    url(r'^api/get_task_list$', views.api_get_task_list, name='api_get_task_list'),
    url(r'^api/get_task_status$', views.api_get_task_status, name='api_get_task_status'),
    url(r'^api/train_model$', views.api_train_model, name='api_train_model'),
    url(r'^api/train_tagger$', views.api_train_tagger, name='api_train_tagger'),
    url(r'^api/apply$', views.api_apply, name='api_apply'),
]
