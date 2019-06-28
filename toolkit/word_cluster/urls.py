from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register('word_clusters', views.WordClusterViewSet, base_name='word_cluster')
