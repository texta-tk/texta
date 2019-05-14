from django.contrib.auth.models import User

def create_test_user(name: str, email: str, password: str):
    '''Creates an User for Testing'''
    user = User.objects.create(username=name, email=email)
    user.set_password(password)
    user.save()
    return user
