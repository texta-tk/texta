from django.contrib.auth.decorators import login_required
from django.urls import include, path
from django.views.static import serve
from django.conf.urls import url
from rest_framework import routers

from toolkit.core.urls import router as core_router, urls as core_urls
from toolkit.embedding.urls import router as embedding_router
from toolkit.tagger.urls import router as tagger_router
from toolkit.neurotagger.urls import router as neurotagger_router
from toolkit.settings import MEDIA_DIR, MEDIA_URL


@login_required
def protected_serve(request, path, document_root=None, show_indexes=False):
    return serve(request, path, document_root, show_indexes)


router = routers.DefaultRouter()
router.registry.extend(core_router.registry)
router.registry.extend(embedding_router.registry)
router.registry.extend(tagger_router.registry)
router.registry.extend(neurotagger_router.registry)

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    url(r'^%s(?P<path>.*)$' % MEDIA_URL, protected_serve, {'document_root': MEDIA_DIR}),
    path('rest-auth/', include('rest_auth.urls')),
    path('rest-auth/registration/', include('rest_auth.registration.urls')),
    path('', include(router.urls)),
    path('', include(core_urls)),
]
