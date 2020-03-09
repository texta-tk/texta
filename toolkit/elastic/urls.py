from rest_framework import routers

from . import views


router = routers.DefaultRouter()
router.register('reindexer', views.ReindexerViewSet, base_name='reindexer')
router.register("index", views.IndexViewSet, base_name="index")
