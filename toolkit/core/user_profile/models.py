from django.db import models
from django.contrib.auth.models import User
# from toolkit.core.project.models import Project

# Create your models here
class UserProfile(models.Model):
    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name='profile')
    # Project as string, to avoid circular import
    active_project = models.ForeignKey('project.Project', on_delete=models.SET_NULL, blank=True, null=True, related_name='activated_by')

    def __str__(self):
        return f'Profile - {self.user.username}'
