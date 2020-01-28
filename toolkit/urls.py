from django.urls import path, include
from django.conf.urls import url
from django.views.static import serve
from django.contrib.auth.decorators import login_required

from toolkit.settings import MEDIA_DIR, MEDIA_URL


@login_required
def protected_serve(request, path, document_root=None, show_indexes=False):
    return serve(request, path, document_root, show_indexes)


urlpatterns = [
    # protected media
    url(r'^%s(?P<path>.*)$' % MEDIA_URL, protected_serve, {'document_root': MEDIA_DIR}),
    # static
    url(r'static/(?P<path>.*)$', serve, {'document_root': 'static'}),
    path('api/v1/', include(('toolkit.urls_v1', 'toolkit_v1'), namespace='v1')),
    # add new versions here
]
