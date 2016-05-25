from django.conf.urls import patterns, url

from . import views


urlpatterns = [
    url(r'^$', views.index,name="home"),
    url(r'update$', views.update, name='update'),
]
