from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register('taggers', views.TaggerViewSet, base_name='tagger')
