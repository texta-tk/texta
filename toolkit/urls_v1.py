from django.conf.urls import url
from django.urls import include, path
from django.views.static import serve
from rest_framework_nested import routers

from toolkit.core.core_variable.views import CoreVariableViewSet
from toolkit.core.health.views import HealthView
from toolkit.core.project.views import ProjectViewSet
from toolkit.core.task.views import TaskAPIView
from toolkit.core.urls import router as core_router
from toolkit.core.user_profile import views as profile_views
from toolkit.dataset_import.urls import router as dataset_import_router
from toolkit.elastic.urls import index_router, router as reindexer_router
from toolkit.elastic.views import ElasticGetIndices
from toolkit.embedding.urls import embedding_router
from toolkit.mlp.urls import mlp_router
from toolkit.mlp.views import MLPListProcessor, MlpDocsProcessor
from toolkit.tagger.urls import router as tagger_router
from toolkit.tools.swagger import schema_view
from toolkit.topic_analyzer.views import ClusterViewSet, ClusteringViewSet
from toolkit.torchtagger.urls import router as torchtagger_router
from toolkit.regex_tagger.urls import router as regex_tagger_router
from toolkit.anonymizer.urls import router as anonymizer_router
from toolkit.uaa_auth.views import UAAView, RefreshUAATokenView


router = routers.DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')
router.register('users', profile_views.UserViewSet, basename='user')
router.register('core_variables', CoreVariableViewSet, basename='corevariable')

# add resources to projects
project_router = routers.NestedDefaultRouter(router, r'projects', lookup='project')
project_router.registry.extend(embedding_router.registry)
project_router.registry.extend(reindexer_router.registry)
project_router.registry.extend(dataset_import_router.registry)
project_router.registry.extend(tagger_router.registry)
project_router.registry.extend(core_router.registry)
project_router.registry.extend(torchtagger_router.registry)
project_router.registry.extend(mlp_router.registry)
project_router.registry.extend(regex_tagger_router.registry)
project_router.registry.extend(anonymizer_router.registry)

# TODO Look for putting this into a better place.
project_router.register(r'clustering', ClusteringViewSet, basename='clustering')
clustering_router = routers.NestedSimpleRouter(project_router, r'clustering', lookup='clustering')
clustering_router.register("clusters", ClusterViewSet, basename="cluster")

app_name = 'toolkit_v1'

urlpatterns = [
    # documentation
    url(r'^swagger(?P<format>\.json|\.yaml)$', schema_view.without_ui(cache_timeout=0), name='schema-json'),
    url(r'^swagger/$', schema_view.with_ui('swagger', cache_timeout=0), name='schema-swagger-ui'),
    url(r'^redoc/$', schema_view.with_ui('redoc', cache_timeout=0), name='schema-redoc'),
    # health
    url('health', HealthView.as_view()),
    # auth
    path('rest-auth/', include('rest_auth.urls')),
    path('rest-auth/registration/', include('rest_auth.registration.urls')),
    path("task/", TaskAPIView.as_view(), name="task_api"),
    path("mlp/texts/", MLPListProcessor.as_view(), name="mlp_texts"),
    path("mlp/docs/", MlpDocsProcessor.as_view(), name="mlp_docs"),
    url(r'^get_indices', ElasticGetIndices.as_view(), name="get_indices_for_project_creation"),
    # routers
    url(r'^', include(router.urls)),
    path("", include(index_router.urls), name="index"),
    url(r'^', include(project_router.urls)),
    url(r'^', include(clustering_router.urls)),

    # UAA OAuth 2.0
    url('uaa/callback', UAAView.as_view()),
    url('uaa/refresh-token', RefreshUAATokenView.as_view()),
]
