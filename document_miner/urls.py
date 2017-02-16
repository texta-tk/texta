from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'listing', views.get_saved_searches, name='get_saved_searches'),
    url(r'query$', views.query, name='query'),
]
