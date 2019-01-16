from django.conf.urls import url

from searcher import views


urlpatterns = [
    url(r'^$', views.index, name='index'),
    url(r'search', views.search, name='search'),
    url(r'mlt_query', views.mlt_query, name='mlt_query'),
    url(r'cluster_query', views.cluster_query, name='cluster_query'),
    url(r'remove_by_query', views.remove_by_query, name='remove_by_query'),
    url(r'get_query', views.get_query, name='get_query'),
    url(r'aggregate', views.aggregate, name='aggregate'),
    url(r'save', views.save, name='save'),
    url(r'delete$', views.delete, name='delete'),
    url(r'delete_facts$', views.delete_facts, name='delete_facts'),
    url(r'fact_to_doc$', views.fact_to_doc, name='fact_to_doc'),
    url(r'autocomplete', views.autocomplete, name='autocomplete'),
    url(r'listing', views.get_saved_searches, name='get_saved_searches'),
    url(r'table_content', views.get_table_content, name='get_table_content'),
    url(r'table_header$', views.get_table_header, name='get_table_header'),
    url(r'table_header_mlt$', views.table_header_mlt, name='table_header_mlt'),
    url(r'export', views.export_pages, name='export_pages'),
    url(r'get_srch_query', views.get_search_query, name='get_search_query'),
    url(r'fact_graph$', views.fact_graph, name='fact_graph'),
    url(r'dashboard$', views.dashboard_endpoint, name='dashboard'),
    url(r'dashboard_visualize', views.dashboard_visualize, name='dashboard_visualize'),
    url(r'delete_document', views.delete_document, name='delete_document'),
]
