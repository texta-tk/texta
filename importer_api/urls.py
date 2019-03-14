from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'document_insertion', views.ImporterApiView.as_view(), name='importer'),
    url(r'analyzers', views.get_analyzer_names, name="list_analyzers")
]
