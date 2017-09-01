from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^search', views.search, name='search'),
    url(r'^aggregate', views.aggregate, name='aggregate'),
    url(r'^list/datasets', views.list_datasets, name='list_datasets'),
    url(r'^list/(?P<dataset_id>\d+)/fields', views.list_fields, name='list_fields'),
]
