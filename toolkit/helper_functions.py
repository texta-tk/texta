from urllib.parse import urljoin
import os
import sys
import re


def apply_celery_task(task_func, *args):
    if not 'test' in sys.argv:
        return task_func.apply_async(args=(*args,))
    else:
        return task_func.apply(args=(*args,))


def get_indices_from_object(model_object):
    """
    Returns indices from object if present.
    If no indices, returns all project indices.
    """
    model_object_indices = model_object.get_indices()
    if model_object_indices:
        return model_object_indices
    else:
        return model_object.project.get_indices()


def parse_list_env_headers(env_key: str, default_value: list) -> list:
    """
    Function for handling env values that need to be stored as a list.

    :param env_key: key of the env value you need to parse.
    :param default_value: in case the key is missing or false, what list value to return
    """

    data = os.getenv(env_key, None)
    if data and isinstance(data, str):
        return data.split(",")
    else:
        return default_value


def add_finite_url_to_feedback(decision_dict, request):
    """
    Adds finite url to feedback.
    """
    if "feedback" in decision_dict:
        feedback = decision_dict["feedback"]
        url = "/api/v1/"+feedback["url"]
        url = re.sub('/+', '/', url)
        decision_dict["feedback"]["url"] = request.build_absolute_uri(url)
    return decision_dict


def get_core_setting(setting_name):
    """
    Retrieves value for a variable from core settings.
    :param: str variable_name: Name for the variable whose value will be returned.
    """
    # import here to avoid import loop
    from toolkit.core.environment_variable.models import EnvironmentVariable
    from toolkit.settings import CORE_SETTINGS
    # retrieve variable setting from db
    variable_match = EnvironmentVariable.objects.filter(name=setting_name)
    # return value from env if no setting in db
    if not variable_match:
        return CORE_SETTINGS[setting_name]
    else:
        return variable_match[0].value
