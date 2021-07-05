from rest_framework import serializers


QUEUE_STAT_CHOICES = (
    ("active", "active"),
    ("scheduled", "scheduled"),
    ("reserved", "reserved"),
    ("stats", "stats")
)


class QueueStatsSerializer(serializers.Serializer):
    method = serializers.ChoiceField(choices=QUEUE_STAT_CHOICES, help_text="Which stat method to look into (active, scheduled, reserved, stats).")
