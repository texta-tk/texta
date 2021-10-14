from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register('crf_extractors', views.CRFExtractorViewSet, basename='crf_extractor')
