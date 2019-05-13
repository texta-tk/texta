from rest_framework import serializers
from toolkit.core.user_profile.models import UserProfile

class UserProfileSerializer(serializers.HyperlinkedModelSerializer):
    username = serializers.ReadOnlyField(source='user.username')
    email = serializers.EmailField(read_only=True, source='user.email')
    date_joined = serializers.ReadOnlyField(source='user.date_joined')
    active_project = serializers.PrimaryKeyRelatedField(read_only=True)

    class Meta:
        model = UserProfile
        fields = ('url', 'id', 'username', 'email', 'active_project', 'date_joined')
