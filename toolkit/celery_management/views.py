# Create your views here.
import logging

from rest_framework import permissions, status, views
from rest_framework.exceptions import APIException
from rest_framework.renderers import BrowsableAPIRenderer, HTMLFormRenderer, JSONRenderer
from rest_framework.response import Response

from toolkit.celery_management.serializers import QueueStatsSerializer
from toolkit.serializer_constants import EmptySerializer
from toolkit.settings import ERROR_LOGGER


class PurgeTasks(views.APIView):
    """
    This will purge ALL the tasks inside Celery as it's difficult to focus down on a specific
    worker instead.
    """
    serializer_class = EmptySerializer
    renderer_classes = (JSONRenderer, BrowsableAPIRenderer, HTMLFormRenderer)
    permission_classes = (permissions.IsAdminUser,)


    def post(self, request):
        try:
            from toolkit.taskman import app
            purged_task_count = app.control.purge()
            message = f"Purged {purged_task_count} tasks from all of Celerys workers!"
            return Response({"detail": message}, status=status.HTTP_200_OK)
        except Exception as e:
            logging.getLogger(ERROR_LOGGER).exception(e)
            raise APIException(str(e))


class QueueStats(views.APIView):
    """
    Returns common stats about queues like how many tasks are active, scheduled or reserved.
    """
    serializer_class = QueueStatsSerializer
    renderer_classes = (JSONRenderer, BrowsableAPIRenderer, HTMLFormRenderer)
    permission_classes = (permissions.IsAdminUser,)


    def post(self, request):
        try:
            from toolkit.taskman import app
            serializer = QueueStatsSerializer(data=request.data)
            serializer.is_valid(raise_exception=False)

            inspector = app.control.inspect()
            method_name = serializer.validated_data["method"]
            method_function = getattr(inspector, method_name)
            response = method_function()
            message = {"detail": "Nothing to report on, is the connection correct?"}

            if not response:
                return Response(message, status=status.HTTP_404_NOT_FOUND)

            return Response(response, status=status.HTTP_200_OK)

        except Exception as e:
            logging.getLogger(ERROR_LOGGER).exception(e)
            raise APIException(str(e))
