from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'search', views.search, name='search'),
    url(r'aggregate', views.aggregate, name='aggregate'),
    url(r'save', views.save, name='save'),
    url(r'delete', views.delete, name='delete'),
    url(r'autocomplete', views.autocomplete, name='autocomplete'),
    url(r'listing', views.get_saved_searches, name='get_saved_searches'),
    url(r'get_examples', views.get_examples, name='get_examples'),
    url(r'examples', views.get_examples_table, name='get_examples_table'),
    url(r'export', views.export_pages, name='export_pages'),
]
