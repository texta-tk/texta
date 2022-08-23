from rest_framework import serializers

from toolkit.core.task.choices import TASK_API_ERROR, TASK_API_STEP_KEYWORDS
from toolkit.core.task.models import Task


class TaskSerializer(serializers.HyperlinkedModelSerializer):
    class Meta:
        model = Task
        fields = ('id', 'status', 'progress', 'step', 'task_type', 'errors', 'time_started', 'last_update', 'time_completed', 'total', 'num_processed')
        read_only_fields = ('id', 'status', 'step', 'task_type', 'errors', 'time_started', 'last_update', 'time_completed')


class TaskAPISerializer(serializers.Serializer):
    task_id = serializers.CharField(required=True, help_text="ID of the Task on which to update the progress")
    authtoken_hash = serializers.CharField(required=True, help_text="Hash of authtoken to authorize if the task owner is sending the payloads.")
    progress = serializers.IntegerField(required=True, help_text="By how much the task progress should be updated with?")
    step = serializers.ChoiceField(required=True, choices=TASK_API_STEP_KEYWORDS, help_text="Keyword to specify whether to update progress, set to complete or enter error.")
    error = serializers.CharField(required=False, help_text="In case the external task fails, this value will contain the error message to be saved.")


    def validate(self, data):
        """
        Force the error step to be used with an error field inside the payload.
        """
        if data["step"] == TASK_API_ERROR:
            if "error" not in data:
                raise serializers.ValidationError("Step field is set to 'error' but could not find the 'error' field containing the message.")
        return data
