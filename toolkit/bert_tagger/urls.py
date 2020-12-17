from rest_framework import routers
from . import views

router = routers.DefaultRouter()
router.register('bert_taggers', views.BertTaggerViewSet, basename='bert_tagger')
