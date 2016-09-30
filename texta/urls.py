from django.conf.urls import include, url
from django.contrib import admin
from django.views import static

urlpatterns = [
    url(r'', include('texta.home.urls')),
    url(r'lm', include('texta.lm.urls')),
    url(r'conceptualiser', include('texta.conceptualiser.urls')),
    url(r'mwe_miner', include('texta.mwe_miner.urls')),
    url(r'corpus_tool', include('texta.corpus_tool.urls')),
    url(r'account', include('texta.account.urls')),
    url(r'model_manager', include('texta.model_manager.urls')),
    url(r'ontology_viewer', include('texta.ontology_viewer.urls')),
    url(r'^admin/', include(admin.site.urls)),
    url(r'^permission_admin/', include('texta.permission_admin.urls')),
    url(r'^grammar_builder/', include('texta.grammar_builder.urls')),
    url(r'^document_miner/', include('texta.document_miner.urls')),
    url(r'static/(?P<path>.*)$',static.serve,{'document_root': 'static'})
]
