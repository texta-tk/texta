from django.conf.urls import url

from . import views
from django.contrib.auth.views import PasswordResetConfirmView, PasswordResetView, PasswordResetDoneView, PasswordResetCompleteView

urlpatterns = [
    url(r'^$', views.index,name="home"),
    url(r'update$', views.update, name='update'),
    url(r'create$', views.create, name="create"),
    url(r'login$', views.login, name="login"),
    url(r'log_out$', views.log_out, name="log_out"),
    url(r'change_password$', views.change_password, name="change_password"),
    url(r'get_auth_token$', views.get_auth_token, name="get_auth_token"),
    url(r'revoke_auth_token$', views.revoke_auth_token, name="revoke_auth_token"),
    url(r'password_reset$', PasswordResetView.as_view(template_name='password-templates/password-form.html',email_template_name='password-templates/password-email.html'), name='password_reset'),
    url(r'password_reset_done/', PasswordResetDoneView.as_view(template_name='password-templates/password-reset-done.html'), name='password_reset_done'),
    url(r'password_reset_confirm/(?P<uidb64>[0-9A-Za-z_\-]+)/(?P<token>[0-9A-Za-z]{1,13}-[0-9A-Za-z]{1,20})/$',
        PasswordResetConfirmView.as_view(template_name="password-templates/password-reset-confirm.html"),
        name='password_reset_confirm'),
    url(r'password_reset_complete$', PasswordResetCompleteView.as_view(template_name='password-templates/password-reset-complete.html'), name='password_reset_complete'),
    ]   
