from django.conf.urls import url

from dataset_importer import views


urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^import$', views.import_dataset, name='import_dataset'),
    url(r'^reload_table$', views.reload_table, name='reload_table'),
    url(r'^remove_import_job$', views.remove_import_job, name='remove_import_job'),
]
