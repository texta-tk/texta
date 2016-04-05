from django.conf.urls import url

from account.views import *


urlpatterns = [
    url(r'create$',create,name="create"),
    url(r'login$',login,name="login"),
    url(r'log_out$',log_out,name="log_out"),
    url(r'change_password$', change_password,name="change_password"),
]
