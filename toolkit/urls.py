from django.urls import include, path
from django.conf.urls import url
from rest_framework import routers

from toolkit.core.health.views import HealthView
from toolkit.core.urls import router as core_router, urls as core_urls
from toolkit.embedding.urls import router as embedding_router
from toolkit.tagger.urls import router as tagger_router
from toolkit.hybrid.urls import router as hybrid_router
#from toolkit.nexus.urls import router as nexus_router

router = routers.DefaultRouter()
router.registry.extend(core_router.registry)
router.registry.extend(embedding_router.registry)
router.registry.extend(hybrid_router.registry)
router.registry.extend(tagger_router.registry)
#router.registry.extend(nexus_router.registry)

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path('rest-auth/', include('rest_auth.urls')),
    path('rest-auth/registration/', include('rest_auth.registration.urls')),
    path('', include(core_urls))
]

