from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^document_insertion', views.ImporterApiView.as_view(), name='importer')
]
