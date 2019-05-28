from django.contrib.auth.models import User
from rest_framework import serializers
# from toolkit.core.user_profile.models import UserProfile

# class UserProfileSerializer(serializers.HyperlinkedModelSerializer):
#     username = serializers.ReadOnlyField(source='user.username')
#     email = serializers.EmailField(read_only=True, source='user.email')
#     date_joined = serializers.ReadOnlyField(source='user.date_joined')
#     active_project = serializers.PrimaryKeyRelatedField(read_only=True)

#     class Meta:
#         model = UserProfile
#         fields = ('url', 'id', 'username', 'email', 'active_project', 'date_joined')


class UserSerializer(serializers.HyperlinkedModelSerializer):
    active_project = serializers.PrimaryKeyRelatedField(read_only=True, source='profile.active_project')

    class Meta:
        model = User
        fields = ('url', 'id', 'username', 'email', 'date_joined', 'active_project')
        read_only_fields = ('username', 'email', 'date_joined',)
