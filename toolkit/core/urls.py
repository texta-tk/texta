from django.urls import path, include
from rest_framework import routers
from toolkit.core.user_profile import views as profile_views
from toolkit.core.project import views as project_views
from toolkit.core.lexicon import views as lexicon_views
from toolkit.core.health.views import HealthView

router = routers.DefaultRouter()
router.register('users', profile_views.UserViewSet, base_name='user')
router.register('projects', project_views.ProjectViewSet, base_name='project')
router.register('lexicons', lexicon_views.LexiconViewSet, base_name='lexicon')

urls = [
    path('health', HealthView.as_view())
]
