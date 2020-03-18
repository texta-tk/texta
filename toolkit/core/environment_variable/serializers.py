from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from ..choices import ENV_VARIABLE_CHOICES
from .models import EnvironmentVariable


class EnvironmentVariableSerializer(serializers.HyperlinkedModelSerializer):
    
    name = serializers.ChoiceField(
        help_text='Name of the environment variable.',
        choices=ENV_VARIABLE_CHOICES,
        validators=[UniqueValidator(queryset=EnvironmentVariable.objects.all())],
        required=True)

    value = serializers.CharField(
        help_text='Value of the environment variable.',
        required=True)

    class Meta:
        model = EnvironmentVariable
        fields = ('url', 'name', 'value')
