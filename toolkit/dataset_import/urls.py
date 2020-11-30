from rest_framework_nested import routers
from . import views

router = routers.DefaultRouter()
router.register('dataset_imports', views.DatasetImportViewSet, basename='dataset_import')
