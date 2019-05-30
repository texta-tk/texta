from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register('taggers', views.TaggerViewSet, base_name='tagger')
router.register('tagger-groups', views.TaggerGroupViewSet, base_name='tagger-group')
