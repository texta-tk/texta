from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'load$', views.load_terms, name='load_terms'),
    url(r'get_lexicons$', views.get_lexicons, name='get_lexicons'),
    url(r'save$', views.save_concepts, name='save'),
]
