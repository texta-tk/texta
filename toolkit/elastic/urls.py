from rest_framework import routers

from . import views
from toolkit.elastic.reindexer import views as reindexer_views
from toolkit.elastic.index_splitter import views as index_splitter_views
from toolkit.elastic.face_analyzer import views as face_analyzer_views

reindexer_router = routers.DefaultRouter()
reindexer_router.register('reindexer', reindexer_views.ReindexerViewSet, basename='reindexer')

index_router = routers.DefaultRouter()
index_router.register("index", views.IndexViewSet, basename="index")

splitter_router = routers.DefaultRouter()
splitter_router.register('index_splitter', index_splitter_views.IndexSplitterViewSet, basename='index_splitter')
