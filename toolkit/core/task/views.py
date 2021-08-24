import logging

from django.db import transaction
from django.utils.timezone import now
from rest_framework.generics import GenericAPIView
from rest_framework.response import Response
from rest_framework.exceptions import PermissionDenied

from toolkit.core.task.choices import TASK_API_COMPLETION, TASK_API_ERROR, TASK_API_PROGRESS
from toolkit.core.task.models import Task
from toolkit.core.task.serializers import TaskAPISerializer, TaskSerializer
from toolkit.settings import ERROR_LOGGER


class TaskAPIView(GenericAPIView):
    serializer_class = TaskAPISerializer
    authentication_classes = []
    permission_classes = []


    def get_queryset(self):
        return Task.objects.all()


    def get(self, request):
        tasks = Task.objects.all().order_by("pk")
        serializer = TaskSerializer(data=tasks, many=True)
        serializer.is_valid()
        return Response(serializer.data)


    def post(self, request):
        serializer = TaskAPISerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        task_id = serializer.validated_data["task_id"]
        amount_of_docs = serializer.validated_data["progress"]
        step = serializer.validated_data["step"]

        authtoken_hash = serializer.validated_data["authtoken_hash"]
        task_authtoken = Task.objects.values_list("authtoken_hash", flat=True).get(pk=task_id).hex

        if authtoken_hash != task_authtoken:
            logging.getLogger(ERROR_LOGGER).error("{} does not match the stored Task authtoken of {}.".format(authtoken_hash, task_authtoken))
            raise PermissionDenied("Authtokens do not match.")

        # To avoid concurrent request updating stale data in the database,
        # we lock and block the rows until the update is finished and the lock
        # is released.
        if step == TASK_API_PROGRESS:
            with transaction.atomic():
                lock = Task.objects.select_for_update().filter(id=task_id)[0]
                lock.num_processed += amount_of_docs
                lock.last_update = now()
                lock.save()
            return Response("Updated task successfully with progress at {}%!".format(lock.progress))

        elif step == TASK_API_COMPLETION:
            with transaction.atomic():
                lock = Task.objects.select_for_update().filter(id=task_id)[0]
                lock.complete()
            return Response("Set task state to completion!")

        elif step == TASK_API_ERROR:
            with transaction.atomic():
                lock = Task.objects.select_for_update().filter(id=task_id)[0]
                lock.add_error(serializer.validated_data["error"])
            return Response("Updated the task with the error!")
