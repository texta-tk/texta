from django.urls import path, include
from rest_framework import routers
from toolkit.core.lexicon import views as lexicon_views
from toolkit.core.search import views as search_views

router = routers.DefaultRouter()
router.register('lexicons', lexicon_views.LexiconViewSet, basename='lexicon')
router.register('searches', search_views.SearchViewSet, basename='search')
