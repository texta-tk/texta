from django.urls import include, path
from rest_framework import routers

# import views
from toolkit.core import views as core_views
from toolkit.datasets import views as datasets_views

router = routers.DefaultRouter()
router.register(r'users', core_views.UserViewSet)
router.register(r'projects', core_views.ProjectViewSet)
router.register(r'datasets', datasets_views.DatasetViewSet)

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path('', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework'))
]