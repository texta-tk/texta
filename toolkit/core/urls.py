from django.urls import path, include
from rest_framework import routers
from toolkit.core.user_profile import views as profile_views
from toolkit.core.project import views as project_views

router = routers.DefaultRouter()
router.register('user', profile_views.UserProfileViewSet)
router.register('project', project_views.ProjectViewSet, base_name='project')
