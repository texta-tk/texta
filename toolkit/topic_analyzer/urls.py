from rest_framework import routers
from . import views


clustering_router = routers.DefaultRouter()
clustering_router.register('clustering', views.ClusteringViewSet, base_name='clustering')
clustering_router.register("cluster", views.ClusterViewSet, base_name="cluster")
