from rest_framework_nested import routers
from . import views

mlp_router = routers.DefaultRouter()
mlp_router.register('mlp', views.MLPElasticViewset, base_name='mlp')
