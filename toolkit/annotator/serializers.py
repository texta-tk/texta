from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from toolkit.annotator.models import Annotator


class AnnotatorSerializer(serializers.ModelSerializer):


    def validate(self, attrs: dict):
        annotator_type = attrs["annotation_type"]
        if annotator_type == "binary":
            if not attrs.get("binary_configuration", None):
                raise ValidationError("When choosing the binary annotation, relevant configurations must be added!")
        elif annotator_type == "multilabel":
            if not attrs.get("multilabel_configuration", None):
                raise ValidationError("When choosing the binary annotation, relevant configurations must be added!")
        elif annotator_type == "entity":
            if not attrs.get("entity_configuration", None):
                raise ValidationError("When choosing the entity annotation, relevant configurations must be added!")
        return attrs


    class Meta:
        model = Annotator
        fields = "__all__"
        read_only_fields = ["annotator_users", "author", "total", "num_processed", "skipped", "created_at", "modified_at", "completed_at"]
