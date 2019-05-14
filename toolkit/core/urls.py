from django.urls import path, include
from rest_framework import routers
from toolkit.core.user_profile import views as profile_views
from toolkit.core.project import views as project_views

router = routers.DefaultRouter()
router.register('users', profile_views.UserProfileViewSet)
router.register('projects', project_views.ProjectViewSet, base_name='project')

urlpatterns = [
    path('', include(router.urls)),
]
