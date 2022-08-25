from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from toolkit.core.user_profile.models import UserProfile


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    """When User object is created, create a UserProfile"""
    if created:
        user_profile = UserProfile.objects.create(user=instance)
        user_profile.uuid = UserProfile.create_uuid()
        user_profile.save()


@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except AttributeError:
        user_profile = UserProfile.objects.create(user=instance)
        user_profile.uuid = UserProfile.create_uuid()
        user_profile.save()
