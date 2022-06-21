from django.conf.urls import url
from django.urls import include, path
from rest_framework_nested import routers

from toolkit.annotator.urls import router as annotator_router
from toolkit.annotator.views import AnnotatorProjectViewset
from toolkit.anonymizer.urls import router as anonymizer_router
from toolkit.bert_tagger.urls import router as bert_tagger_router
from toolkit.celery_management.views import CeleryQueueCount, CeleryStats, PurgeTasks, QueueDetailStats
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
from toolkit.dataset_import.views import DatasetImportViewSet
from toolkit.docparser.views import DocparserView
from toolkit.elastic.analyzers.views import ApplyEsAnalyzerOnIndices, SnowballProcessor
from toolkit.elastic.document_importer.views import DocumentImportView, DocumentInstanceView, UpdateSplitDocument
from toolkit.elastic.document_api.views import AddFactsView, DeleteFactsByQueryViewset, DeleteFactsView, DocumentImportView, DocumentInstanceView, EditFactsByQueryViewset, UpdateFactsView, UpdateSplitDocument
from toolkit.elastic.index.views import ElasticGetIndices
from toolkit.elastic.index_splitter.views import IndexSplitterViewSet
from toolkit.elastic.reindexer.views import ReindexerViewSet
from toolkit.elastic.search_tagger.views import SearchFieldsTaggerViewSet, SearchQueryTaggerViewSet
from toolkit.elastic.urls import index_router
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
from toolkit.crf_extractor.urls import router as crf_router
from toolkit.uaa_auth.views import RefreshUAATokenView, UAAView


router = routers.DefaultRouter()
router.register("annotator_projectlist", AnnotatorProjectViewset, basename="annotator-project-list")
router.register(r'projects', ProjectViewSet, basename='project')
router.register('users', profile_views.UserViewSet, basename='user')
router.register('core_variables', CoreVariableViewSet, basename='corevariable')

# add resources to projects
project_router = routers.NestedDefaultRouter(router, r'projects', lookup='project')
project_router.registry.extend(embedding_router.registry)
project_router.registry.extend(embedding_router.registry)
project_router.registry.extend(tagger_router.registry)
project_router.registry.extend(annotator_router.registry)
project_router.registry.extend(rakun_extractor_router.registry)
project_router.registry.extend(core_router.registry)
project_router.registry.extend(torchtagger_router.registry)
project_router.registry.extend(mlp_router.registry)
project_router.registry.extend(regex_tagger_router.registry)
project_router.registry.extend(anonymizer_router.registry)
project_router.registry.extend(bert_tagger_router.registry)
project_router.registry.extend(evaluator_router.registry)
project_router.registry.extend(summarizer_router.registry)
project_router.registry.extend(crf_router.registry)

# elastic resources
project_router.register('elastic/dataset_imports', DatasetImportViewSet, basename='dataset_import')
project_router.register('elastic/reindexer', ReindexerViewSet, basename='reindexer')
project_router.register('elastic/dataset_imports', DatasetImportViewSet, basename='dataset_import')
project_router.register('elastic/index_splitter', IndexSplitterViewSet, basename='index_splitter')
project_router.register('elastic/apply_analyzers', ApplyEsAnalyzerOnIndices, basename='apply_analyzers')
project_router.register('elastic/search_query_tagger', SearchQueryTaggerViewSet, basename='search_query_tagger')
project_router.register('elastic/search_fields_tagger', SearchFieldsTaggerViewSet, basename='search_fields_tagger')
project_router.register('elastic/delete_facts_by_query', DeleteFactsByQueryViewset, basename='delete_facts_by_query')
project_router.register('elastic/edit_facts_by_query', EditFactsByQueryViewset, basename='edit_facts_by_query')

# TODO Look for putting this into a better place.
project_router.register(r'topic_analyzer', TopicAnalyzerViewset, basename='topic_analyzer')
clustering_router = routers.NestedSimpleRouter(project_router, r'topic_analyzer', lookup='topic_analyzer')
clustering_router.register("clusters", ClusterViewSet, basename="cluster")

app_name = 'toolkit_v2'

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
    # mlp
    path("mlp/texts/", MLPListProcessor.as_view(), name="mlp_texts"),
    path("mlp/docs/", MlpDocsProcessor.as_view(), name="mlp_docs"),
    path("mlp/detect_lang/", LangDetectView.as_view(), name="mlp_detect_lang"),
    # summarizer
    path("summarizer/summarize", SummarizerSummarize.as_view(), name="summarizer_summarize"),
    # routers
    url(r'^', include(router.urls)),
    path("elastic/", include(index_router.urls), name="elastic_index"),
    url(r'^', include(project_router.urls)),
    url(r'^', include(clustering_router.urls)),

    # Elasticsearch related content.
    path("elastic/snowball/", SnowballProcessor.as_view(), name="snowball"),
    path('elastic/docparser/', DocparserView.as_view(), name="docparser"),
    path('projects/<int:pk>/elastic/documents/', DocumentImportView.as_view(), name="document_import"),
    path('projects/<int:pk>/elastic/documents/<str:index>/<str:document_id>/', DocumentInstanceView.as_view(), name="document_instance"),
    path('projects/<int:pk>/elastic/documents/<str:index>/update_split', UpdateSplitDocument.as_view(), name="update_split_document"),
    path('projects/<int:pk>/elastic/documents/<str:index>/<str:document_id>/delete_facts', DeleteFactsView.as_view(), name="delete_facts"),
    path('projects/<int:pk>/elastic/documents/<str:index>/<str:document_id>/update_facts', UpdateFactsView.as_view(), name="update_facts"),
    path('projects/<int:pk>/elastic/documents/<str:index>/<str:document_id>/add_facts', AddFactsView.as_view(), name="add_facts"),


    # Previous projects extra actions.
    path('projects/<int:project_pk>/elastic/export_search/', ExportSearchView.as_view(), name="project-export-search"),
    path('projects/<int:project_pk>/elastic/document/', DocumentView.as_view(), name="project-document"),
    path('projects/<int:project_pk>/elastic/get_spam/', GetSpamView.as_view(), name="project-get-spam"),
    path('projects/<int:project_pk>/elastic/get_facts/', GetFactsView.as_view(), name="get_facts"),
    path('projects/<int:project_pk>/elastic/aggregate_facts/', AggregateFactsView.as_view(), name="aggregate_facts"),
    path('projects/<int:project_pk>/elastic/get_fields/', GetFieldsView.as_view(), name="get_fields"),
    path('projects/<int:project_pk>/elastic/get_indices/', GetIndicesView.as_view(), name="get_project_indices"),
    path('elastic/get_indices/', ElasticGetIndices.as_view(), name="get_indices_for_project_creation"),
    path('projects/<int:project_pk>/elastic/scroll/', ScrollView.as_view(), name="project-scroll"),
    path('projects/<int:project_pk>/elastic/search/', SearchView.as_view(), name="search"),
    path('projects/<int:project_pk>/elastic/search_by_query/', SearchByQueryView.as_view(), name="search_by_query"),

    # Celery resources
    path('celery/queue/purge_tasks/', PurgeTasks.as_view(), name="purge_tasks"),
    path('celery/queue/stats/', QueueDetailStats.as_view(), name="queue_stats"),
    path('celery/queue/count_tasks/', CeleryQueueCount.as_view(), name="count_tasks"),
    path('celery/stats/', CeleryStats.as_view(), name="celery_stats"),

    # UAA OAuth 2.0
    url('uaa/callback', UAAView.as_view()),
    url('uaa/refresh-token', RefreshUAATokenView.as_view()),
]
