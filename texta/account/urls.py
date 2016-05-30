from django.conf.urls import url

from . import views


urlpatterns = [
    url(r'create$', views.create, name="create"),
    url(r'login$', views.login, name="login"),
    url(r'log_out$', views.log_out, name="log_out"),
    url(r'change_password$', views.change_password, name="change_password"),
]
