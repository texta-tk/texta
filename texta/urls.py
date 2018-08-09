from django.contrib.auth.decorators import login_required
from django.views.static import serve
from django.conf.urls import include, url
from django.contrib import admin
from django.views import static

from lexicon_miner.urls import urlpatterns as lm_urls
from account.urls import urlpatterns as account_urls
from conceptualiser.urls import urlpatterns as conceptualiser_urls
from mwe_miner.urls import urlpatterns as mwe_miner_urls
from searcher.urls import urlpatterns as searcher_urls
from ontology_viewer.urls import urlpatterns as ontology_viewer_urls
from permission_admin.urls import urlpatterns as permission_admin_urls
from grammar_builder.urls import urlpatterns as grammar_builder_urls
from search_api.urls import urlpatterns as search_api_urls
from dataset_importer.urls import urlpatterns as dataset_importer_urls
from texta import settings


@login_required
def protected_serve(request, path, document_root=None, show_indexes=False):
    return serve(request, path, document_root, show_indexes)


urlpatterns = [
    url(r'', include('account.urls')),
    url(r'lexicon_miner', include('lexicon_miner.urls')),
    url(r'conceptualiser', include('conceptualiser.urls')),
    url(r'mwe_miner', include('mwe_miner.urls')),
    url(r'^searcher', include('searcher.urls')),
    url(r'ontology_viewer', include('ontology_viewer.urls')),
    url(r'^permission_admin/', include('permission_admin.urls')),
    url(r'^grammar_builder/', include('grammar_builder.urls')),
    url(r'^api/', include('search_api.urls')),
    url(r'^dataset_importer/', include('dataset_importer.urls')),
    url(r'static/(?P<path>.*)$',static.serve,{'document_root': 'static'}),
    url(r'^%s(?P<path>.*)$' % settings.MEDIA_URL, protected_serve, {'document_root': settings.PROTECTED_MEDIA}),
    url(r'^import_api/', include('importer_api.urls')),
    url(r'^task_manager/', include('task_manager.urls')),
]
