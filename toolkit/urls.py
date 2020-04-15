from django.urls import path, include
from django.views.generic.base import RedirectView


urlpatterns = [
    # reroute root to version prefix
    path('', RedirectView.as_view(url='api/v1/', permanent=False), name='index'),
    path('api/v1/', include(('toolkit.urls_v1', 'toolkit_v1'), namespace='v1')),
    # add new versions here
]
