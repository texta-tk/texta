from rest_framework_nested import routers
from . import views

embedding_router = routers.DefaultRouter()
embedding_router.register('embeddings', views.EmbeddingViewSet, basename='embedding')
