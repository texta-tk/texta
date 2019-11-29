from django.contrib.auth.models import User
from rest_framework import serializers


class UserSerializer(serializers.HyperlinkedModelSerializer):
    is_superuser = serializers.SerializerMethodField()

    class Meta:
        model = User
        fields = ('url', 'id', 'username', 'email', 'date_joined', 'is_superuser')
        read_only_fields = ('username', 'email', 'date_joined')

    def get_is_superuser(self, obj):
        return obj.is_superuser
