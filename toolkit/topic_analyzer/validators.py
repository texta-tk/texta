from rest_framework.exceptions import ValidationError

from toolkit.topic_analyzer.models import Cluster


def check_cluster_existence(value):
    cluster = Cluster.objects.filter(pk=value)
    if not cluster:
        raise ValidationError(f"Could not find cluster with ID: {cluster}")
