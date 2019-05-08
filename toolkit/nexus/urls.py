from django.urls import path, include
from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register('nexus', views.EntityViewSet, base_name='nexus')

urlpatterns = [
    path('', include(router.urls)),
]
