from django.contrib.auth.decorators import login_required
from django.urls import include, path
from django.views.static import serve
from django.conf.urls import url
from rest_framework_nested import routers

from toolkit.core.urls import router as core_router
from toolkit.embedding.urls import embedding_router
from toolkit.tagger.urls import router as tagger_router
from toolkit.elastic.urls import router as reindexer_router
from toolkit.dataset_import.urls import router as dataset_import_router
from toolkit.neurotagger.urls import router as neurotagger_router
from toolkit.core.user_profile import views as profile_views
from toolkit.core.health.views import HealthView
from toolkit.elastic.views import ElasticGetIndices
from toolkit.core.project.views import ProjectViewSet
from toolkit.core.user_profile.views import UserViewSet
from toolkit.embedding.views import EmbeddingViewSet
from toolkit.settings import MEDIA_DIR, MEDIA_URL
from toolkit.tools.swagger import schema_view


@login_required
def protected_serve(request, path, document_root=None, show_indexes=False):
    return serve(request, path, document_root, show_indexes)


router = routers.DefaultRouter()
router.register(r'projects', ProjectViewSet, base_name='project')
router.register('users', profile_views.UserViewSet, base_name='user')

project_router = routers.NestedDefaultRouter(router, r'projects', lookup='project')
project_router.registry.extend(embedding_router.registry)
project_router.registry.extend(reindexer_router.registry)
project_router.registry.extend(dataset_import_router.registry)
project_router.registry.extend(tagger_router.registry)
project_router.registry.extend(core_router.registry)
project_router.registry.extend(neurotagger_router.registry)


urlpatterns = [
    # documentation
    url(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    url(r'^swagger/$', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    url(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    # protected media
    url(r'^%s(?P<path>.*)$' % MEDIA_URL, protected_serve, {'document_root': MEDIA_DIR}),
    # static
    url(r'static/(?P<path>.*)$',serve,{'document_root': 'static'}),
    # health
    url('health', HealthView.as_view()),
    # auth
    path('rest-auth/', include('rest_auth.urls')),
    path('rest-auth/registration/', include('rest_auth.registration.urls')),
    # elastic
    # TODO Admin access only
    url(r'^get_indices', ElasticGetIndices.as_view()),
    # routers
    url(r'^', include(router.urls)),
    url(r'^', include(project_router.urls))
]
