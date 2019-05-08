from django.urls import include, path
from django.conf.urls import url

# Wire up our API using automatic URL routing.
# Additionally, we include login URLs for the browsable API.
urlpatterns = [
    path('', include('toolkit.core.urls')),
    path('', include('toolkit.nexus.urls')),
    path('', include('toolkit.embedding.urls')),
    path('rest-auth/', include('rest_auth.urls')),
    path('rest-auth/registration/', include('rest_auth.registration.urls'))
]
