from django.contrib.auth.decorators import login_required
from django.urls import include, path
from django.views.static import serve
from django.conf.urls import url
from rest_framework_nested import routers

from toolkit.core.urls import router as core_router
from toolkit.embedding.urls import embedding_router
from toolkit.tagger.urls import router as tagger_router
from toolkit.core.user_profile import views as profile_views
from toolkit.core.health.views import HealthView
from toolkit.core.project.views import ProjectViewSet
from toolkit.core.user_profile.views import UserViewSet
from toolkit.embedding.views import EmbeddingViewSet
from toolkit.settings import MEDIA_DIR, MEDIA_URL


@login_required
def protected_serve(request, path, document_root=None, show_indexes=False):
    return serve(request, path, document_root, show_indexes)


router = routers.DefaultRouter()
router.register(r'projects', ProjectViewSet, base_name='project')
router.register('users', profile_views.UserViewSet, base_name='user')

project_router = routers.NestedDefaultRouter(router, r'projects', lookup='project')
project_router.registry.extend(embedding_router.registry)
project_router.registry.extend(tagger_router.registry)
project_router.registry.extend(core_router.registry)

urlpatterns = [
    url(r'^%s(?P<path>.*)$' % MEDIA_URL, protected_serve, {'document_root': MEDIA_DIR}),
    url(r'static/(?P<path>.*)$',serve,{'document_root': 'static'}),
    url('health', HealthView.as_view()),
    path('rest-auth/', include('rest_auth.urls')),
    path('rest-auth/registration/', include('rest_auth.registration.urls')),
    url(r'^', include(router.urls)),
    url(r'^', include(project_router.urls))
]
