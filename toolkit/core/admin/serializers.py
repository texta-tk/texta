from rest_framework import serializers

from toolkit.core.choices import ENV_VARIABLE_CHOICES


class EnvironmentVariableSerializer(serializers.Serializer):
    
    name = serializers.ChoiceField(
        help_text='Name of the environment variable.',
        choices=ENV_VARIABLE_CHOICES,
        required=True)

    value = serializers.CharField(
        help_text='Value of the environment variable.',
        required=True)
