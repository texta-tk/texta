# Create your views here.
import logging

from rest_framework import permissions, status, views
from rest_framework.exceptions import APIException
from rest_framework.renderers import BrowsableAPIRenderer, HTMLFormRenderer, JSONRenderer
from rest_framework.response import Response

from toolkit.permissions.project_permissions import IsSuperUser
from toolkit.serializer_constants import EmptySerializer
from toolkit.settings import CELERY_LONG_TERM_TASK_QUEUE, CELERY_MLP_TASK_QUEUE, CELERY_SHORT_TERM_TASK_QUEUE, ERROR_LOGGER


class PurgeTasks(views.APIView):
    """
    This will purge ALL the tasks inside Celery as it's difficult to focus down on a specific
    worker or queue instead.
    """
    serializer_class = EmptySerializer
    renderer_classes = (JSONRenderer, BrowsableAPIRenderer, HTMLFormRenderer)
    permission_classes = (IsSuperUser,)


    def post(self, request):
        try:
            from toolkit.taskman import app
            purged_task_count = app.control.purge()
            message = f"Purged {purged_task_count} tasks from all of Celerys workers!"
            return Response({"detail": message}, status=status.HTTP_200_OK)
        except Exception as e:
            logging.getLogger(ERROR_LOGGER).exception(e)
            raise APIException(str(e))


class QueueDetailStats(views.APIView):
    """
    Returns common stats about queues like how many tasks are active or reserved.
    """
    serializer_class = EmptySerializer
    renderer_classes = (JSONRenderer, BrowsableAPIRenderer, HTMLFormRenderer)
    permission_classes = (IsSuperUser,)


    def post(self, request):
        try:
            from toolkit.taskman import app

            response = {}
            inspector = app.control.inspect()
            methods = ["active", "reserved"]
            for method in methods:
                method_function = getattr(inspector, method)
                result = method_function()
                if result:
                    response[method] = result

            message = {"detail": "Nothing to report on, is the connection correct?"}

            if not response:
                return Response(message, status=status.HTTP_404_NOT_FOUND)

            return Response(response, status=status.HTTP_200_OK)

        except Exception as e:
            logging.getLogger(ERROR_LOGGER).exception(e)
            raise APIException(str(e))


class CeleryStats(views.APIView):
    """
    Returns information about the Celery instances themselves, like how many processes
    are running, total task counts etc.
    """
    serializer_class = EmptySerializer
    renderer_classes = (JSONRenderer, BrowsableAPIRenderer, HTMLFormRenderer)
    permission_classes = (IsSuperUser,)


    def post(self, request):
        try:
            from toolkit.taskman import app

            inspector = app.control.inspect()
            response = inspector.stats()
            message = {"detail": "Nothing to report on, is the connection correct?"}

            if not response:
                return Response(message, status=status.HTTP_404_NOT_FOUND)

            return Response(response, status=status.HTTP_200_OK)

        except Exception as e:
            logging.getLogger(ERROR_LOGGER).exception(e)
            raise APIException(str(e))


class CeleryQueueCount(views.APIView):
    """
    Returns common stats about queues like how many tasks are active, scheduled or reserved.
    """
    serializer_class = EmptySerializer
    renderer_classes = (JSONRenderer, BrowsableAPIRenderer, HTMLFormRenderer)
    permission_classes = (permissions.IsAuthenticated,)


    def _count_tasks_in_queue(self, result: dict):
        base_dict = {
            CELERY_SHORT_TERM_TASK_QUEUE: 0,
            CELERY_LONG_TERM_TASK_QUEUE: 0,
            CELERY_MLP_TASK_QUEUE: 0
        }

        for hostname, task_infos in result.items():
            for task in task_infos:
                delivery_info = task.get("delivery_info", {})
                queue_name = delivery_info.get("routing_key", None)
                if queue_name and queue_name in base_dict:
                    base_dict[queue_name] += 1
        return base_dict


    def _return_base(self):
        base_dict = {"active": 0, "reserved": 0, "scheduled": 0}
        response = {
            CELERY_SHORT_TERM_TASK_QUEUE: base_dict.copy(),
            CELERY_LONG_TERM_TASK_QUEUE: base_dict.copy(),
            CELERY_MLP_TASK_QUEUE: base_dict.copy()
        }
        return response


    def post(self, request):
        try:
            from toolkit.taskman import app

            container = self._return_base()
            methods = ["active", "reserved", "scheduled"]
            inspector = app.control.inspect()

            for method in methods:
                inspect_function_body = getattr(inspector, method)
                inspect_result = inspect_function_body()
                if inspect_result:
                    queue_count = self._count_tasks_in_queue(inspect_result)
                    if queue_count:
                        # We enforce a queue: stat structure here because
                        # the requirements changed in-between.
                        for queue_name, count in queue_count.items():
                            container[queue_name][method] += count

            if not container:
                message = {"detail": "Nothing to report on, is the connection correct?"}
                return Response(message, status=status.HTTP_404_NOT_FOUND)

            return Response(container, status=status.HTTP_200_OK)

        except Exception as e:
            logging.getLogger(ERROR_LOGGER).exception(e)
            raise APIException(str(e))
