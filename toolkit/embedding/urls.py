from django.urls import path, include
from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register('embedding', views.EmbeddingViewSet, base_name='project-embedding')

urlpatterns = [
    path('', include(router.urls)),
]
