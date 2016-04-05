from django.conf.urls import patterns, url

from home.views import *


urlpatterns = [
    url(r'^$',index,name="home"),
    url(r'update$',update, name='update'),
]
