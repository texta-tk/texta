from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register('torchtaggers', views.TorchTaggerViewSet, basename='torchtagger')
