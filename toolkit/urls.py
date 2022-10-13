from django.conf.urls import url
from django.urls import include, path
from django.views.generic.base import RedirectView
from django.views.static import serve

from toolkit.core.project.views import ProtectedFileServe, ProtectedServeApi
from toolkit.settings import MEDIA_DIR, MEDIA_URL


urlpatterns = [
    # protected media
    url(r'^%s(?P<path>.*)$' % MEDIA_URL, ProtectedServeApi.as_view(), {'document_root': MEDIA_DIR}),
    path('data/projects/<int:project_id>/<str:application>/<str:file_name>', ProtectedFileServe.as_view(), {'document_root': "data/projects/"}, name="protected_serve"),

    # static
    url(r'^static/(?P<path>.*)$', serve, {'document_root': 'static'}),

    # reroute root to version prefix
    path('', RedirectView.as_view(url='api/v2/', permanent=False), name='index'),
    path('api/v1/', include(('toolkit.urls_v1', 'toolkit_v1'), namespace='v1')),
    path('api/v2/', include(('toolkit.urls_v2', 'toolkit_v2'), namespace='v2')),

    # add new versions here
]
