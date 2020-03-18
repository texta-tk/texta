from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from ..choices import CORE_VARIABLE_CHOICES
from .models import CoreVariable
from ...settings import CORE_SETTINGS
from ..health.utils import get_elastic_status, get_mlp_status


class CoreVariableSerializer(serializers.HyperlinkedModelSerializer):
    
    name = serializers.ChoiceField(
        help_text="Name of the core variable.",
        choices=CORE_VARIABLE_CHOICES,
        validators=[UniqueValidator(queryset=CoreVariable.objects.all())],
        required=True)

    value = serializers.CharField(
        help_text="Value of the core variable.",
        required=True)
    
    env_value = serializers.SerializerMethodField()


    class Meta:
        model = CoreVariable
        fields = ("url", "name", "value", "env_value")

    def get_env_value(self, obj):
        """Retrieves value for the variable from env."""
        variable_name = obj.name
        return CORE_SETTINGS[variable_name]

    def validate(self, data):
        """Validate value by checking the URL availability."""
        value = data["value"]
        service_alive = True
        if data["name"] == "TEXTA_ES_URL":
            service_alive = get_elastic_status(ES_URL=value)["alive"]
        elif data["name"] == "TEXTA_MLP_URL":
            service_alive = get_mlp_status(MLP_URL=value)["alive"]
        # if not alive, raise Error
        if not service_alive:
            raise serializers.ValidationError(f"Entered URL ({value}) for service cannot be reached. Please check the URL.")
        return data
