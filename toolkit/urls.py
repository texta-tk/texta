from django.urls import include, path
from rest_framework import routers

# import views
from toolkit.core import views as core_views

router = routers.DefaultRouter()
router.register(r'user', core_views.UserViewSet)
router.register(r'project', core_views.ProjectViewSet)
router.register(r'dataset', core_views.DatasetViewSet)
router.register(r'search', core_views.SearchViewSet)
router.register(r'embedding', core_views.EmbeddingViewSet)
router.register(r'tagger', core_views.TaggerViewSet)
router.register(r'lexicon', core_views.LexiconViewSet)
router.register(r'phrase', core_views.PhraseViewSet)

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path('', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]