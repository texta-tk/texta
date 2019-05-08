from django.urls import path, include
from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register('user', views.UserViewSet)
router.register('project', views.ProjectViewSet, base_name='project')

urlpatterns = [
    path('', include(router.urls)),
]
