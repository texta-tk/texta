from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register('hybrid-tagger', views.HybridTaggerViewSet, base_name='hybrid-tagger')
