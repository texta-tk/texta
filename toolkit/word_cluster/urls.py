from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register('word-clusters', views.WordClusterViewSet, base_name='word_cluster')
