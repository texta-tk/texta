from rest_framework import routers
from . import views


clustering_router = routers.DefaultRouter()
clustering_router.register('clustering', views.ClusteringViewSet, basename='clustering')
clustering_router.register("cluster", views.ClusterViewSet, basename="cluster")
