from rest_framework import routers

from toolkit.elastic.index import views as index_views
from toolkit.elastic.reindexer import views as reindexer_views
from toolkit.elastic.index_splitter import views as index_splitter_views
from toolkit.elastic.search_tagger import views as search_tagger_views

reindexer_router = routers.DefaultRouter()
reindexer_router.register('reindexer', reindexer_views.ReindexerViewSet, basename='reindexer')

index_router = routers.DefaultRouter()
index_router.register("index", index_views.IndexViewSet, basename="index")

splitter_router = routers.DefaultRouter()
splitter_router.register('index_splitter', index_splitter_views.IndexSplitterViewSet, basename='index_splitter')

search_tagger_router = routers.DefaultRouter()
search_tagger_router.register('search_query_tagger', search_tagger_views.SearchQueryTaggerViewSet, basename='search_query_tagger')
search_tagger_router.register('search_fields_tagger', search_tagger_views.SearchFieldsTaggerViewSet, basename='search_fields_tagger')
