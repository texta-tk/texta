from django.contrib.auth.models import User
from rest_framework import serializers


class UserSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = User
        fields = ('url', 'id', 'username', 'email', 'date_joined', 'is_superuser', 'last_login')
        read_only_fields = ('username', 'email', 'date_joined', 'last_login')
