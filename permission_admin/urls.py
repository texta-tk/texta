from django.conf.urls import url

from permission_admin.views import *


urlpatterns = [
    url(r'^$', index, name='index'),
    url(r'^save_permissions/?', save_permissions),
    url(r'^delete_user/?', delete_user),
    url(r'^add_dataset/?', add_dataset),
    url(r'^delete_dataset/?', delete_dataset),
]
