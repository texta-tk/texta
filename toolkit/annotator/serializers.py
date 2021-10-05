import json

from django.urls import reverse
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from toolkit.annotator.models import Annotator, BinaryAnnotatorConfiguration, EntityAnnotatorConfiguration, MultilabelAnnotatorConfiguration
from toolkit.core.project.models import Project
from toolkit.core.user_profile.serializers import UserSerializer
from toolkit.elastic.index.models import Index
from toolkit.elastic.index.serializers import IndexSerializer
from toolkit.elastic.tools.searcher import EMPTY_QUERY, ElasticSearcher
from toolkit.elastic.validators import check_for_existence
from toolkit.serializer_constants import FieldValidationSerializer


ANNOTATION_MAPPING = {
    "entity": EntityAnnotatorConfiguration,
    "multilabel": MultilabelAnnotatorConfiguration,
    "binary": BinaryAnnotatorConfiguration
}


class DocumentIDSerializer(serializers.Serializer):
    document_id = serializers.CharField()


class BinaryAnnotationSerializer(serializers.Serializer):
    document_id = serializers.CharField()
    annotation_type = serializers.ChoiceField(choices=(
        ("pos", "pos"),
        ("neg", "neg"))
    )


class EntityAnnotationSerializer(serializers.Serializer):
    document_id = serializers.CharField()
    # Add proper validation for the structure here.
    spans = serializers.ListSerializer(child=serializers.IntegerField(), default=[0, 0])
    fact_name = serializers.CharField()
    fact_value = serializers.CharField()


class MultilabelAnnotatorConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = MultilabelAnnotatorConfiguration
        fields = "__all__"


class BinaryAnnotatorConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = BinaryAnnotatorConfiguration
        fields = "__all__"


class EntityAnnotatorConfigurationSerializer(serializers.ModelSerializer):
    class Meta:
        model = EntityAnnotatorConfiguration
        fields = ("fact_name",)


class AnnotatorSerializer(FieldValidationSerializer, serializers.ModelSerializer):
    binary_configuration = BinaryAnnotatorConfigurationSerializer(required=False)
    multilabel_configuration = MultilabelAnnotatorConfigurationSerializer(required=False)
    entity_configuration = EntityAnnotatorConfigurationSerializer(required=False)
    url = serializers.SerializerMethodField()
    annotator_users = UserSerializer(many=True, read_only=True)
    author = UserSerializer(read_only=True)

    query = serializers.JSONField(help_text='Query in JSON format', required=False, default=json.dumps(EMPTY_QUERY))

    indices = IndexSerializer(
        many=True,
        default=[],
        help_text="Which indices to use for this procedure.",
        validators=[
            check_for_existence
        ]
    )


    def get_url(self, obj):
        index = reverse(f"v2:annotator-detail", kwargs={"project_pk": obj.project.pk, "pk": obj.pk})
        if "request" in self.context:
            request = self.context["request"]
            url = request.build_absolute_uri(index)
            return url
        else:
            return None


    def __get_configurations(self, validated_data):
        # Get what type of annotation is used.
        annotator_type = validated_data["annotation_type"]
        # Generate the model field name of the respective annotators conf.
        configuration_field = f"{annotator_type}_configuration"
        # Remove it from the validated_data so it wouldn't be fed into the model, bc it only takes a class object.
        configurations = validated_data.pop(configuration_field)
        # Fetch the proper configuration class and populate it with the fields.
        configuration = ANNOTATION_MAPPING[annotator_type](**configurations)
        configuration.save()
        return {configuration_field: configuration}


    def __get_total(self, indices, query):
        ec = ElasticSearcher(indices=indices, query=query)
        return ec.count()


    def create(self, validated_data):
        request = self.context.get('request')
        project_pk = request.parser_context.get('kwargs').get("project_pk")
        project_obj = Project.objects.get(id=project_pk)

        indices = [index["name"] for index in validated_data["indices"]]
        indices = project_obj.get_available_or_all_project_indices(indices)
        validated_data.pop("indices")

        configuration = self.__get_configurations(validated_data)
        total = self.__get_total(indices=indices, query=json.loads(validated_data["query"]))

        annotator = Annotator.objects.create(
            **validated_data,
            author=request.user,
            project=project_obj,
            total=total,
            **configuration,
        )

        annotator.annotator_users.add(request.user)

        for index in Index.objects.filter(name__in=indices, is_open=True):
            annotator.indices.add(index)

        annotator.save()

        annotator.add_annotation_mapping(indices)

        return annotator


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
        fields = (
            'id',
            'url',
            'author',
            'description',
            'indices',
            'field',
            'query',
            'annotation_type',
            'annotator_users',
            'created_at',
            'modified_at',
            'completed_at',
            'total',
            'annotated',
            'skipped',
            'validated',
            'binary_configuration',
            "multilabel_configuration",
            "entity_configuration",
            "bulk_size",
            "es_timeout"
        )
        read_only_fields = ["annotator_users", "author", "total", "annotated", "validated", "skipped", "created_at", "modified_at", "completed_at"]
