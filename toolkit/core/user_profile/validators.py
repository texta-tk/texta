from typing import List

from django.contrib.auth.models import User
from rest_framework.exceptions import ValidationError


def check_if_username_exist(username: List[str]):
    if User.objects.filter(username=username).exists():
        return True
    else:
        raise ValidationError("Username does not match available users!")
