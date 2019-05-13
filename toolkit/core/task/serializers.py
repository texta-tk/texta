from rest_framework import serializers

from toolkit.core.task.models import Task

class TaskSerializer(serializers.HyperlinkedModelSerializer):
    status = serializers.CharField(read_only=True)
    progress = serializers.FloatField(read_only=True)
    step = serializers.CharField(read_only=True)
    time_started = serializers.DateTimeField(read_only=True)
    last_update = serializers.DateTimeField(read_only=True)
    time_completed = serializers.DateTimeField(read_only=True)

    class Meta:
        model = Task
        fields = ('id', 'status', 'progress', 'step', 'time_started', 'last_update', 'time_completed')
