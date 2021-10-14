from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register('rakun_extractors', views.RakunExtractorViewSet, basename='rakun_extractor')
