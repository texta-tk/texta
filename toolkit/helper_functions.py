import os
import sys


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
    object_indices = model_object.project.get_indices()
    if object_indices:
        return object_indices
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
