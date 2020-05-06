from django.conf.urls import url
from django.contrib.auth.decorators import login_required
from django.urls import include, path
from django.views.generic.base import RedirectView
from django.views.static import serve

from toolkit.settings import MEDIA_DIR, MEDIA_URL


@login_required
def protected_serve(request, path, document_root=None, show_indexes=False):
    return serve(request, path, document_root, show_indexes)


urlpatterns = [
    # reroute root to version prefix
    path('', RedirectView.as_view(url='api/v1/', permanent=False), name='index'),
    path('api/v1/', include(('toolkit.urls_v1', 'toolkit_v1'), namespace='v1')),
    url(r'^%s(?P<path>.*)$' % MEDIA_URL, protected_serve, {'document_root': MEDIA_DIR}),

    # add new versions here
]
