import re

from rest_framework import serializers
from rest_framework.validators import UniqueValidator

from .models import CoreVariable
from ..choices import CORE_VARIABLE_CHOICES
from ..health.utils import get_elastic_status
from ...helper_functions import is_secret_core_setting, encrypt
from ...settings import CORE_SETTINGS


class CoreVariableSerializer(serializers.HyperlinkedModelSerializer):
    name = serializers.ChoiceField(
        help_text="Name of the core variable.",
        choices=CORE_VARIABLE_CHOICES,
        validators=[UniqueValidator(queryset=CoreVariable.objects.all())],
        required=True)

    value = serializers.CharField(
        help_text="Value of the core variable.",
        required=False)

    env_value = serializers.SerializerMethodField()

    class Meta:
        model = CoreVariable
        fields = ("url", "name", "value", "env_value")

    def get_env_value(self, obj):
        """Retrieves value for the variable from env."""
        variable_name = obj.name
        env_value = CORE_SETTINGS.get(variable_name, "")
        if env_value and is_secret_core_setting(variable_name):
            return encrypt(env_value)
        return env_value

    def update(self, instance, validated_data):
        setting_name = validated_data["name"]
        if is_secret_core_setting(setting_name):
            validated_data["value"] = encrypt(validated_data["value"])
        return super(CoreVariableSerializer, self).update(instance, validated_data)

    def validate(self, data):
        """Validate value by checking the URL availability."""
        name = data["name"]
        if "value" not in data:
            value = ""
            data["value"] = ""
        else:
            value = data["value"]
        # check if urls not empty
        if name in ("TEXTA_ES_URL") and not value:
            raise serializers.ValidationError(f"Value for param {name} should not be empty.")
        # check if not any metasymbols ES_PREFIX
        if name == "TEXTA_ES_PREFIX" and re.escape(value) != value:
            raise serializers.ValidationError(f"Entered value should not contain metasymbols.")
        service_alive = True
        if name == "TEXTA_ES_URL":
            service_alive = get_elastic_status(uri=value)["alive"]
            if service_alive is False:
                raise serializers.ValidationError(f"Invalid TEXTA_ES_URL {value}")
        if name == "TEXTA_EVALUATOR_MEMORY_BUFFER_GB":
            if value:
                try:
                    float_value = float(value)
                except ValueError:
                    raise serializers.ValidationError(f"The value inside the string should be either a float or an integer.")

        # if not alive, raise Error
        if not service_alive:
            raise serializers.ValidationError(f"Entered URL ({value}) for service cannot be reached. Please check the URL.")

        return data
