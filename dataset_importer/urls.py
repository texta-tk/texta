from django.conf.urls import url

from dataset_importer import views


urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^import$', views.import_dataset, name='import_dataset'),
]
