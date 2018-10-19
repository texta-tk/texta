from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'^$', views.index,name="home"),
    url(r'update$', views.update, name='update'),
    url(r'create$', views.create, name="create"),
    url(r'login$', views.login, name="login"),
    url(r'log_out$', views.log_out, name="log_out"),
    url(r'change_password$', views.change_password, name="change_password"),
    url(r'get_auth_token$', views.get_auth_token, name="get_auth_token"),
    url(r'revoke_auth_token$', views.revoke_auth_token, name="revoke_auth_token"),
    url(r'reset_password$', views.send_password_reset_email, name="send_password_reset_email"),
    url(r'password_reset_confirm/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$', views.password_reset_confirm, name="password_reset_confirm"),
    
]

""" url(r'reset_password/<uidb64>/<token>/', views.password_reset_confirm,name='password_reset_confirm') """