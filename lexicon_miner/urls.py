from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'new$', views.newLexicon, name='newLexicon'),
    url(r'delete', views.deleteLexicon, name='deleteLexicon'),
    url(r'save$', views.saveLexicon, name='saveLexicon'),
    url(r'select', views.selectLexicon, name='selectLexicon'),
    url(r'query$', views.query, name='query'),
    url(r'reset_suggestions', views.reset_suggestions, name="reset_suggestions"),
]
