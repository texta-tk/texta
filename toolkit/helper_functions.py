import os
import re
from typing import List

from django.contrib.auth.decorators import login_required
from django.views.static import serve


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
        url = "/api/v1/" + feedback["url"]
        url = re.sub('/+', '/', url)
        decision_dict["feedback"]["url"] = request.build_absolute_uri(url)
    return decision_dict


def get_core_setting(setting_name):
    """
    Retrieves value for a variable from core settings.
    :param: str variable_name: Name for the variable whose value will be returned.
    """
    # import here to avoid import loop
    from toolkit.core.core_variable.models import CoreVariable
    from toolkit.settings import CORE_SETTINGS
    # retrieve variable setting from db
    try:
        variable_match = CoreVariable.objects.filter(name=setting_name)
        if not variable_match:
            # return value from env if no setting record in db
            return CORE_SETTINGS[setting_name]
        elif not variable_match[0].value:
            # return value from env if value in record None
            return CORE_SETTINGS[setting_name]
        else:
            # return value from db
            return variable_match[0].value
    except Exception as e:
        return CORE_SETTINGS[setting_name]


@login_required
def protected_serve(request, path, document_root=None, show_indexes=False):
    return serve(request, path, document_root, show_indexes)


def download_mlp_requirements(model_directory: str, supported_langs: List[str], logger):
    from texta_mlp.mlp import MLP, ENTITY_MAPPER_DATA_URLS
    MLP.download_entity_mapper_resources(model_directory, entity_mapper_urls=ENTITY_MAPPER_DATA_URLS, logger=logger)
    MLP.download_stanza_resources(model_directory, supported_langs=supported_langs, logger=logger)
