from django.conf.urls import url
from django.urls import include, path
from rest_framework_nested import routers

from toolkit.anonymizer.urls import router as anonymizer_router
from toolkit.bert_tagger.urls import router as bert_tagger_router
from toolkit.core.core_variable.views import CoreVariableViewSet
from toolkit.core.health.views import HealthView
from toolkit.core.project.views import (
    AggregateFactsView,
    DocumentView,
    ExportSearchView,
    GetFactsView,
    GetFieldsView,
    GetIndicesView,
    GetSpamView,
    ProjectViewSet,
    ScrollView,
    SearchByQueryView,
    SearchView
)
from toolkit.core.task.views import TaskAPIView
from toolkit.core.urls import router as core_router
from toolkit.core.user_profile import views as profile_views
from toolkit.crf_extractor.urls import router as crf_router
from toolkit.dataset_import.urls import router as dataset_import_router
from toolkit.docparser.views import DocparserView
from toolkit.elastic.analyzers.urls import snowball_router as apply_snowball
from toolkit.elastic.analyzers.views import SnowballProcessor
from toolkit.elastic.document_api.views import DocumentImportView, DocumentInstanceView, UpdateSplitDocument
from toolkit.elastic.document_importer.views import DocumentImportView, DocumentInstanceView, UpdateSplitDocument
from toolkit.elastic.index.views import ElasticGetIndices
from toolkit.elastic.urls import index_router, reindexer_router, search_tagger_router, splitter_router
from toolkit.embedding.urls import embedding_router
from toolkit.evaluator.urls import router as evaluator_router
from toolkit.mlp.urls import mlp_router
from toolkit.mlp.views import LangDetectView, MLPListProcessor, MlpDocsProcessor
from toolkit.rakun_keyword_extractor.urls import router as rakun_extractor_router
from toolkit.regex_tagger.urls import router as regex_tagger_router
from toolkit.summarizer.urls import router as summarizer_router
from toolkit.summarizer.views import SummarizerSummarize
from toolkit.tagger.urls import router as tagger_router
from toolkit.tools.swagger import schema_view
from toolkit.topic_analyzer.views import ClusterViewSet, TopicAnalyzerViewset
from toolkit.torchtagger.urls import router as torchtagger_router
from toolkit.uaa_auth.views import RefreshUAATokenView, UAAView


router = routers.DefaultRouter()
router.register(r'projects', ProjectViewSet, basename='project')
router.register('users', profile_views.UserViewSet, basename='user')
router.register('core_variables', CoreVariableViewSet, basename='corevariable')

# add resources to projects
project_router = routers.NestedDefaultRouter(router, r'projects', lookup='project')
project_router.registry.extend(embedding_router.registry)
project_router.registry.extend(reindexer_router.registry)
project_router.registry.extend(search_tagger_router.registry)
project_router.registry.extend(splitter_router.registry)
project_router.registry.extend(dataset_import_router.registry)
project_router.registry.extend(tagger_router.registry)
project_router.registry.extend(rakun_extractor_router.registry)
project_router.registry.extend(core_router.registry)
project_router.registry.extend(torchtagger_router.registry)
project_router.registry.extend(mlp_router.registry)
project_router.registry.extend(regex_tagger_router.registry)
project_router.registry.extend(anonymizer_router.registry)
project_router.registry.extend(bert_tagger_router.registry)
project_router.registry.extend(evaluator_router.registry)
project_router.registry.extend(summarizer_router.registry)
project_router.registry.extend(apply_snowball.registry)
project_router.registry.extend(crf_router.registry)

# TODO Look for putting this into a better place.
project_router.register(r'clustering', TopicAnalyzerViewset, basename='clustering')
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
    path('rest-auth/', include('dj_rest_auth.urls')),
    path('rest-auth/registration/', include('dj_rest_auth.registration.urls')),
    # tasks
    path("task/", TaskAPIView.as_view(), name="task_api"),
    # elastic stemmer
    path("snowball/", SnowballProcessor.as_view(), name="snowball"),

    # mlp
    path("mlp/texts/", MLPListProcessor.as_view(), name="mlp_texts"),
    path("mlp/docs/", MlpDocsProcessor.as_view(), name="mlp_docs"),
    path("mlp/detect_lang/", LangDetectView.as_view(), name="mlp_detect_lang"),
    url(r'^get_indices', ElasticGetIndices.as_view(), name="get_indices_for_project_creation"),

    # summarizer
    path("summarizer/summarize", SummarizerSummarize.as_view(), name="summarizer_summarize"),
    # routers
    url(r'^', include(router.urls)),
    path("", include(index_router.urls), name="index"),
    url(r'^', include(project_router.urls)),
    url(r'^', include(clustering_router.urls)),
    path('docparser/', DocparserView.as_view(), name="docparser"),

    path('projects/<int:pk>/document_importer/', DocumentImportView.as_view(), name="document_import"),
    path('projects/<int:pk>/document_importer/<str:index>/<str:document_id>/', DocumentInstanceView.as_view(), name="document_instance"),
    path('projects/<int:pk>/document_importer/<str:index>/update_split', UpdateSplitDocument.as_view(), name="update_split_document"),

    # Previous projects extra actions.
    path('projects/<int:project_pk>/export_search/', ExportSearchView.as_view(), name="project-export-search"),
    path('projects/<int:project_pk>/document/', DocumentView.as_view(), name="project-document"),
    path('projects/<int:project_pk>/get_spam/', GetSpamView.as_view(), name="project-get-spam"),
    path('projects/<int:project_pk>/get_facts/', GetFactsView.as_view(), name="get_facts"),
    path('projects/<int:project_pk>/aggregate_facts/', AggregateFactsView.as_view(), name="aggregate_facts"),
    path('projects/<int:project_pk>/get_fields/', GetFieldsView.as_view(), name="get_fields"),
    path('projects/<int:project_pk>/get_indices/', GetIndicesView.as_view(), name="get_project_indices"),
    path('projects/<int:project_pk>/scroll/', ScrollView.as_view(), name="project-scroll"),
    path('projects/<int:project_pk>/search/', SearchView.as_view(), name="search"),
    path('projects/<int:project_pk>/search_by_query/', SearchByQueryView.as_view(), name="search_by_query"),

    # UAA OAuth 2.0
    url('uaa/callback', UAAView.as_view()),
    url('uaa/refresh-token', RefreshUAATokenView.as_view()),
]
