from rest_framework import routers
from . import tagger_views, tagger_group_views

router = routers.DefaultRouter()
router.register('taggers', tagger_views.TaggerViewSet, basename='tagger')
router.register('tagger_groups', tagger_group_views.TaggerGroupViewSet, basename='tagger_group')
