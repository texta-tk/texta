from rest_framework_nested import routers

from . import views


snowball_router = routers.DefaultRouter()
snowball_router.register('apply_snowball', views.ApplySnowballOnIndices, basename='apply_snowball')
