from rest_framework import routers
from .views import RegexTaggerViewSet, RegexTaggerGroupViewSet

router = routers.DefaultRouter()
router.register('regex_taggers', RegexTaggerViewSet, basename='regex_tagger')
router.register('regex_tagger_groups', RegexTaggerGroupViewSet, basename='regex_tagger_group')
