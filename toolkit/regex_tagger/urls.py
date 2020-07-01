from rest_framework import routers
from .views import RegexTaggerViewSet

router = routers.DefaultRouter()
router.register('regex_taggers', RegexTaggerViewSet, basename='regex_tagger')
