from rest_framework import routers
from .views import AnonymizerViewSet

router = routers.DefaultRouter()
router.register('anonymizers', AnonymizerViewSet, basename='anonymizer')
