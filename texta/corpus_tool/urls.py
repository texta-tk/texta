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
    url(r'table_content', views.get_table_content, name='get_table_content'),
    url(r'table_header', views.get_table_header, name='get_table_header'),
    url(r'export', views.export_pages, name='export_pages'),
]
