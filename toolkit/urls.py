from django.urls import path, include


urlpatterns = [
    path('api/v1/', include(('toolkit.urls_v1', 'toolkit_v1'), namespace='v1'))
    # add new versions here
]
