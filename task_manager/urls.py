from django.conf.urls import url

from task_manager import views


urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^start_task$', views.start_task, name='start_task'),
    url(r'^delete_task$', views.delete_task, name='delete_task'),
#    url(r'search', views.search, name='search'),
]
