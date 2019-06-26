from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register('neurotaggers', views.NeurotaggerViewSet, base_name='neurotagger')
