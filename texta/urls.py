from django.conf.urls import include, url
from django.contrib import admin
from django.views import static

urlpatterns = [
    url(r'', include('home.urls')),
    url(r'lm', include('lm.urls')),
    url(r'conceptualiser', include('conceptualiser.urls')),
    url(r'mwe_miner', include('mwe_miner.urls')),
    url(r'corpus_tool', include('corpus_tool.urls')),
    url(r'account', include('account.urls')),
    url(r'model_manager', include('model_manager.urls')),
    url(r'classification_manager', include('classification_manager.urls')),
    url(r'ontology_viewer', include('ontology_viewer.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^permission_admin/', include('permission_admin.urls')),
    url(r'^grammar_builder/', include('grammar_builder.urls')),
    url(r'^api/', include('search_api.urls')),
    url(r'^dataset_importer/', include('dataset_importer.urls')),
    url(r'static/(?P<path>.*)$',static.serve,{'document_root': 'static'}),
]
