from rest_framework import routers

from . import views


router = routers.DefaultRouter()
router.register('reindexer', views.ReindexerViewSet, basename='reindexer')

index_router = routers.DefaultRouter()
index_router.register("index", views.IndexViewSet, basename="index")
