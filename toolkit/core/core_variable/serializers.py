from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from ..choices import CORE_VARIABLE_CHOICES
from .models import CoreVariable


class CoreVariableSerializer(serializers.HyperlinkedModelSerializer):
    
    name = serializers.ChoiceField(
        help_text='Name of the core variable.',
        choices=CORE_VARIABLE_CHOICES,
        validators=[UniqueValidator(queryset=CoreVariable.objects.all())],
        required=True)

    value = serializers.CharField(
        help_text='Value of the core variable.',
        required=True)

    class Meta:
        model = CoreVariable
        fields = ('url', 'name', 'value')
