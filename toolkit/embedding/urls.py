from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register('embeddings', views.EmbeddingViewSet, base_name='embedding')
router.register('embedding_clusters', views.EmbeddingClusterViewSet, base_name='embedding_cluster')
