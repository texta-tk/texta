from django.conf.urls import include, url
from django.contrib import admin
from django.views import static

# NEW PY REQUIREMENT
from lm.urls import urlpatterns as lm_urls
from account.urls import urlpatterns as account_urls
from conceptualiser.urls import urlpatterns as conceptualiser_urls
from mwe_miner.urls import urlpatterns as mwe_miner_urls
from searcher.urls import urlpatterns as searcher_urls
from model_manager.urls import urlpatterns as model_manager_urls
from classification_manager.urls import urlpatterns as classification_manager_urls
from ontology_viewer.urls import urlpatterns as ontology_viewer_urls
from permission_admin.urls import urlpatterns as permission_admin_urls
from grammar_builder.urls import urlpatterns as grammar_builder_urls
from search_api.urls import urlpatterns as search_api_urls
from dataset_importer.urls import urlpatterns as dataset_importer_urls

# NEW PY REQUIREMENT
urlpatterns = [
    url(r'', include('account.urls')),
    url(r'lm', include('lm.urls')),
    url(r'conceptualiser', include('conceptualiser.urls')),
    url(r'mwe_miner', include('mwe_miner.urls')),
    url(r'^searcher', include('searcher.urls')),
    url(r'model_manager', include('model_manager.urls')),
    url(r'classification_manager', include('classification_manager.urls')),
    url(r'ontology_viewer', include('ontology_viewer.urls')),
    url(r'^permission_admin/', include('permission_admin.urls')),
    url(r'^grammar_builder/', include('grammar_builder.urls')),
    url(r'^api/', include('search_api.urls')),
    url(r'^dataset_importer/', include('dataset_importer.urls')),
    url(r'static/(?P<path>.*)$',static.serve,{'document_root': 'static'}),
    url(r'^import/', include('importer.urls')),
]

# from django.conf.urls import url
# from django.contrib import admin
# from django.views import static

# urlpatterns = [
#     url(r'lm', lm_urls, name='lm_urls),
#     url(r'', 'account_urls),
#     url(r'conceptualiser', 'conceptualiser_urls),
#     url(r'mwe_miner', 'mwe_miner_urls),
#     url(r'^searcher', 'searcher_urls),
#     url(r'model_manager', 'model_manager_urls),
#     url(r'classification_manager', 'classification_manager_urls),
#     url(r'ontology_viewer', 'ontology_viewer_urls),
#     url(r'^admin/', admin.site.urls),
#     url(r'^permission_admin/', 'permission_admin_urls),
#     url(r'^grammar_builder/', 'grammar_builder_urls),
#     url(r'^api/', 'search_api_urls),
#     url(r'^dataset_importer/', 'dataset_importer_urls),
#     url(r'static/(?P<path>.*)$',static.serve,{'document_root': 'static'}),
# ]
