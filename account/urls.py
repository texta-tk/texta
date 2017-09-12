from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'create$', views.create, name="create"),
    url(r'login$', views.login, name="login"),
    url(r'log_out$', views.log_out, name="log_out"),
    url(r'change_password$', views.change_password, name="change_password"),
    url(r'get_auth_token$', views.get_auth_token, name="get_auth_token"),
    url(r'revoke_auth_token$', views.revoke_auth_token, name="revoke_auth_token"),
]
