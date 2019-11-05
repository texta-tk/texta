from rest_framework import serializers

from toolkit.core.task.models import Task

class TaskSerializer(serializers.HyperlinkedModelSerializer):

    class Meta:
        model = Task
        fields = ('id', 'status', 'progress', 'step', 'errors','time_started', 'last_update', 'time_completed')
        read_only_fields = ('id', 'status', 'progress', 'step', 'errors', 'time_started', 'last_update', 'time_completed')
