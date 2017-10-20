from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'^import$', views.import_dataset, name='import_dataset'),
]
