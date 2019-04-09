from django.urls import include
from django.conf.urls import url
#from rest_framework import routers
from rest_framework_nested import routers

# import views
from toolkit.core import views as core_views
from toolkit.embedding import views as embedding_views
from toolkit.tagger import views as tagger_views
from toolkit.nexus import views as nexus_views

router = routers.DefaultRouter()
router.register(r'user', core_views.UserViewSet)
router.register(r'project', core_views.ProjectViewSet, base_name='project')

#router.register(r'project//embedding', embedding_views.EmbeddingViewSet, base_name='embedding')
#router.register(r'tagger', tagger_views.TaggerViewSet)

project_router = routers.NestedDefaultRouter(router, r'project', lookup='project')
project_router.register(r'embedding', embedding_views.EmbeddingViewSet, base_name='project-embedding')
project_router.register(r'nexus', nexus_views.EntityViewSet, base_name='nexus')
#project_router.register(r'tagger', tagger_views.TaggerViewSet, base_name='project-tagger')


#router.register(r'search', core_views.SearchViewSet)
#router.register(r'lexicon', core_views.LexiconViewSet)
#router.register(r'phrase', core_views.PhraseViewSet)
#router.register(r'task', core_views.TaskViewSet)
#router.register(r'tagger', tagger_views.TaggerViewSet)
#router.register(r'nexus', nexus_views.EntityViewSet, base_name='nexus')

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    url(r'^', include(router.urls)),
    url(r'^', include(project_router.urls)),
    url(r'api-auth/', include('rest_framework.urls', namespace='rest_framework')),
]