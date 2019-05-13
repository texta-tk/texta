from django.db.models.signals import post_save
from django.contrib.auth.models import User
from django.dispatch import receiver
from toolkit.core.user_profile.models import UserProfile


@receiver(post_save, sender=User)
def create_profile(sender, instance, created, **kwargs):
    '''When User object is created, create a UserProfile'''
    if created:
        UserProfile.objects.create(user=instance)


@receiver(post_save, sender=User)
def save_profile(sender, instance, **kwargs):
    try:
        instance.profile.save()
    except AttributeError:
        UserProfile.objects.create(user=instance)
