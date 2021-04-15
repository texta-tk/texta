from rest_framework_nested import routers
from . import views


mlp_router = routers.DefaultRouter()
mlp_router.register('mlp_index', views.MLPElasticWorkerViewset, basename='mlp_index')
mlp_router.register('lang_index', views.ApplyLangOnIndices, basename='lang_index')
