import sys


def apply_celery_task(task_func, *args):
    if not 'test' in sys.argv:
        task_func.apply_async(args=(*args,))
    else:
        task_func.apply(args=(*args,))


def get_indices_from_object(model_object):
    """
    Returns indices from object if present.
    If no indices, returns all project indices.
    """
    object_indices = model_object.project.indices
    if object_indices:
        return object_indices
    else:
        return model_object.project.indices
