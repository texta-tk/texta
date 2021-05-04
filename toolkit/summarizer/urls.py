from rest_framework import routers
from .views import SummarizerIndexViewSet

router = routers.DefaultRouter()
router.register('summarizer_index', SummarizerIndexViewSet, basename='summarizer_index')
