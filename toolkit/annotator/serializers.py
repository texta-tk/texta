import json

from django.urls import reverse
from rest_framework import serializers
from rest_framework.exceptions import ValidationError

from toolkit.annotator.models import Annotator, BinaryAnnotatorConfiguration, Category, Comment, EntityAnnotatorConfiguration, Label, Labelset, MultilabelAnnotatorConfiguration, Record
from toolkit.core.project.models import Project
from toolkit.core.user_profile.serializers import UserSerializer
from toolkit.elastic.index.models import Index
from texta_elastic.searcher import ElasticSearcher
from texta_elastic.aggregator import ElasticAggregator
from toolkit.serializer_constants import FieldParseSerializer, ToolkitTaskSerializer


ANNOTATION_MAPPING = {
    "entity": EntityAnnotatorConfiguration,
    "multilabel": MultilabelAnnotatorConfiguration,
    "binary": BinaryAnnotatorConfiguration
}


class RecordSerializer(serializers.ModelSerializer):

    def to_representation(self, instance: Record):
        data = super(RecordSerializer, self).to_representation(instance)
        data["fact"] = json.loads(data["fact"])
        data["username"] = instance.user.username
        return data


    class Meta:
        model = Record
        fields = "__all__"


class LabelsetSerializer(serializers.Serializer):

    def to_representation(self, instance: Labelset):
        data = super(LabelsetSerializer, self).to_representation(instance)
        data["id"] = instance.category.id
        return data

    class Meta:
        model = Labelset
        fields = "__all__"

    indices = serializers.ListSerializer(child=serializers.CharField(), default="[]", required=False, help_text="List of indices.")
    fact_names = serializers.ListSerializer(child=serializers.CharField(), default="[]", required=False, help_text="List of fact_names.")
    value_limit = serializers.IntegerField(default=500, required=False, help_text="Limit to the number of values added.")
    category = serializers.CharField(help_text="Category name.")
    values = serializers.ListSerializer(child=serializers.CharField(), help_text="Values to be added.")


    def create(self, validated_data):
        indices = validated_data["indices"]
        fact_names = validated_data["fact_names"]
        value_limit = validated_data["value_limit"]
        category = validated_data["category"]
        values = validated_data["values"]

        category, is_created = Category.objects.get_or_create(value=category)

        index_container = []
        value_container = []

        if indices:
            for index in indices:
                try:
                    index_obj = Index.objects.get(name=index)
                except Exception as e:
                    raise serializers.ValidationError(e)
                if fact_names:
                    for fact_name in fact_names:
                        fact_map = ElasticAggregator(indices=index).facts(filter_by_fact_name=fact_name, size=int(value_limit))
                        for factm in fact_map:
                            label, is_created = Label.objects.get_or_create(value=factm)
                            value_container.append(label)
                else:
                    fact_map = ElasticAggregator(indices=index).facts(size=int(value_limit))
                    for fact_name in fact_map:
                        for fact_value in fact_map[fact_name]:
                            label, is_created = Label.objects.get_or_create(value=fact_value)
                            value_container.append(label)
                index_container.append(index_obj)

        for value in values:
            label, is_created = Label.objects.get_or_create(value=value)
            value_container.append(label)

        labelset, is_created = Labelset.objects.get_or_create(category=category)
        labelset.indices.add(*index_container)
        labelset.fact_names = fact_names
        labelset.value_limit = value_limit
        labelset.values.add(*value_container)

        return labelset


class DocumentIDSerializer(serializers.Serializer):
    document_id = serializers.CharField()


class DocumentEditSerializer(serializers.Serializer):
    document_id = serializers.CharField()
    index = serializers.CharField()


class ValidateDocumentSerializer(serializers.Serializer):
    document_id = serializers.CharField()
    facts = serializers.JSONField()
    is_valid = serializers.BooleanField()


class MultilabelAnnotationSerializer(serializers.Serializer):
    document_id = serializers.CharField()
    index = serializers.CharField()
    labels = serializers.ListSerializer(child=serializers.CharField())


class CommentSerializer(serializers.Serializer):
    document_id = serializers.CharField()
    user = UserSerializer(read_only=True, default=serializers.CurrentUserDefault())
    text = serializers.CharField()


    def to_representation(self, instance: Comment):
        return {
            "user": instance.user.username,
            "text": instance.text,
            "document_id": instance.document_id,
            "created_at": instance.created_at
        }


class BinaryAnnotationSerializer(serializers.Serializer):
    document_id = serializers.CharField()
    index = serializers.CharField()
    doc_type = serializers.CharField(default="_doc")
    annotation_type = serializers.ChoiceField(choices=(
        ("pos", "pos"),
        ("neg", "neg"))
    )


class EntityAnnotationSerializer(serializers.Serializer):
    document_id = serializers.CharField()
    index = serializers.CharField()
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


class AnnotatorSerializer(FieldParseSerializer, ToolkitTaskSerializer, serializers.ModelSerializer):
    binary_configuration = BinaryAnnotatorConfigurationSerializer(required=False)
    multilabel_configuration = MultilabelAnnotatorConfigurationSerializer(required=False)
    entity_configuration = EntityAnnotatorConfigurationSerializer(required=False)
    url = serializers.SerializerMethodField()
    annotator_users = UserSerializer(many=True, read_only=True)


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
        fields = validated_data.pop("fields")

        validated_data.pop("indices")

        configuration = self.__get_configurations(validated_data)
        total = self.__get_total(indices=indices, query=json.loads(validated_data["query"]))

        annotator = Annotator.objects.create(
            **validated_data,
            author=request.user,
            project=project_obj,
            total=total,
            fields=json.dumps(fields),
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
            'target_field',
            'fields',
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
        fields_to_parse = ("fields",)


class AnnotatorProjectSerializer(AnnotatorSerializer):


    def to_representation(self, instance: Annotator):
        result = super(AnnotatorProjectSerializer, self).to_representation(instance)
        result["project_pk"] = instance.project.pk
        return result
