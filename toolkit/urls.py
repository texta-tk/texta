from django.urls import include, path
from rest_framework import routers

# import views
from toolkit.core import views as core_views
from toolkit.trainer import views as trainer_views

router = routers.DefaultRouter()
router.register(r'user', core_views.UserViewSet)
router.register(r'project', core_views.ProjectViewSet)
router.register(r'search', core_views.SearchViewSet)
router.register(r'lexicon', core_views.LexiconViewSet)
router.register(r'phrase', core_views.PhraseViewSet)
router.register(r'embedding', trainer_views.EmbeddingViewSet)
router.register(r'tagger', trainer_views.TaggerViewSet)
router.register(r'task', trainer_views.TaskViewSet)

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path('', include(router.urls)),
    path('api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]