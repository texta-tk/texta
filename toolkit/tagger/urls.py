from rest_framework import routers
from . import tagger_views, tagger_group_views

router = routers.DefaultRouter()
router.register('taggers', tagger_views.TaggerViewSet, base_name='tagger')
router.register('tagger_groups', tagger_group_views.TaggerGroupViewSet, base_name='tagger_group')
