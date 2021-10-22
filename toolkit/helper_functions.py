import hashlib
import json
import os
import pathlib
import re
import uuid
from functools import partial
from typing import List, Optional

import elasticsearch_dsl
import psutil
from django.contrib.auth.decorators import login_required
from django.core.exceptions import PermissionDenied
from django.db import connections
from django.views.static import serve
from rest_framework import serializers


def avoid_db_timeout(func):
    def inner_wrapper(*args, **kwargs):
        for conn in connections.all():
            conn.close_if_unusable_or_obsolete()
        func(*args, **kwargs)


    return inner_wrapper


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


def parse_tuple_env_headers(env_key: str, default_value) -> tuple:
    """
    Function for handling env values that need to be stored as a tuple.

    :param env_key: key of the env value you need to parse.
    :param default_value: in case the key is missing or false, what tuple value to return
    """

    data = os.getenv(env_key, None)
    if data and isinstance(data, str):
        res = tuple((first, second) for first, second in json.loads(data))
        return res
    else:
        return default_value


def add_finite_url_to_feedback(decision_dict, request):
    """
    Adds finite url to feedback.
    """
    from toolkit.settings import REST_FRAMEWORK

    if "feedback" in decision_dict:
        feedback = decision_dict["feedback"]
        default_version = REST_FRAMEWORK.get("DEFAULT_VERSION")
        url = f"/api/{default_version}/" + feedback["url"]
        url = re.sub('/+', '/', url)
        decision_dict["feedback"]["url"] = request.build_absolute_uri(url)
    return decision_dict


def get_core_setting(setting_name: str):
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


def set_core_setting(setting_name: str, setting_value: str):
    """
    Set core settings outside of the API.
    :param: str setting name: Name of the variable to update.
    :param: str setting_value: New Value of the variable.
    """
    from toolkit.core.core_variable.models import CoreVariable
    from toolkit.core.core_variable.serializers import CoreVariableSerializer

    # As the new param doesn't actually get passed through the serializer,
    # check if the type is correct
    if not isinstance(setting_value, str):
        raise serializers.ValidationError(f"The type of the value should be {type('')}, not {type(setting_value)}.")

    data = {"name": setting_name, "value": setting_value}

    validated_data = CoreVariableSerializer().validate(data)
    variable_matches = CoreVariable.objects.filter(name=validated_data["name"])

    if not variable_matches:
        # Add a new variable
        new_variable = CoreVariable(name=validated_data["name"], value=validated_data["value"])
        new_variable.save()

    else:
        # Change existing variable
        variable_match = variable_matches[0]
        variable_match.value = validated_data["value"]
        variable_match.save()


@login_required
def protected_serve(request, path, document_root=None, show_indexes=False):
    return serve(request, path, document_root, show_indexes)


@login_required
def protected_file_serve(request, project_id, application, file_name, document_root=None):
    from toolkit.core.project.models import Project
    from django.shortcuts import get_object_or_404

    project = get_object_or_404(Project, pk=project_id)
    user_allowed = project.users.filter(pk=request.user.pk).exists()
    if user_allowed:
        path = pathlib.Path(str(project_id)) / application / file_name
        return serve(request, str(path), document_root)
    else:
        raise PermissionDenied()


def download_mlp_requirements(model_directory: str, supported_langs: List[str], logger):
    from texta_mlp.mlp import MLP, ENTITY_MAPPER_DATA_URLS
    MLP.download_entity_mapper_resources(model_directory, entity_mapper_urls=ENTITY_MAPPER_DATA_URLS, logger=logger)
    MLP.download_stanza_resources(model_directory, supported_langs=supported_langs, logger=logger)


def download_bert_requirements(model_directory: str, supported_models: List[str], cache_directory: str, logger=None, num_labels: int = None):
    """ Download pretrained BERT models & tokenizers.
    """
    from texta_bert_tagger.tagger import BertTagger
    errors, failed_models = BertTagger.download_pretrained_models(bert_models=supported_models, save_dir=model_directory, cache_dir=cache_directory, logger=logger, num_labels=num_labels)
    return (errors, failed_models)


def download_nltk_resources(data_directory: str):
    """ Download NLTK resources.
    """
    import nltk
    punkt_tokenizers_dir = os.path.join(data_directory, "tokenizers", "punkt")
    # Check if the punkt tokenizers already downloaded
    if not os.path.exists(punkt_tokenizers_dir) or not os.listdir(punkt_tokenizers_dir):
        nltk.download("punkt", download_dir=data_directory)
    nltk.data.path.append(data_directory)


def get_downloaded_bert_models(model_directory: str) -> List[str]:
    """ Retrieve list of downloaded pretrained BERT models.
    """
    from texta_bert_tagger.tagger import BertTagger
    normalized_model_names = os.listdir(model_directory)
    bert_models = [BertTagger.restore_name(normalized_name) for normalized_name in normalized_model_names]
    return bert_models


def chunks(lst: list, n: int):
    """Yield successive n-sized chunks from lst."""
    for i in range(0, len(lst), n):
        yield lst[i:i + n]


def chunks_iter(iterator, n: int):
    container = []

    for item in iterator:
        if len(container) <= n:
            container.append(item)
        if len(container) == n:
            yield container
            container = []

    # In case the final batch did not match the n count.
    if container:
        yield container


def hash_file(file, block_size=65536):
    hasher = hashlib.md5()
    for buf in iter(partial(file.read, block_size), b''):
        hasher.update(buf)

    return hasher.hexdigest()


def hash_string(content: str):
    content_bytes = content.encode('utf-8')
    hash_str = hashlib.md5(content_bytes).hexdigest()
    return hash_str


def load_stop_words_from_string(stop_words_string: str) -> List[str]:
    """Loads stop words from whitespace-separated string into list."""
    stop_words = re.split(" |\n|\r\n", stop_words_string)
    stop_words = [stop_word for stop_word in stop_words if stop_word]
    return stop_words


def load_stop_words(stop_words_string: str) -> List[str]:
    """Loads stop words either from regular string or JSON string"""
    try:
        stop_words = json.loads(stop_words_string)
    except:
        stop_words = load_stop_words_from_string(stop_words_string)
    return stop_words


def calculate_memory_buffer(memory_buffer: str = "", ratio: float = 0.5, unit: str = "gb"):
    """
    Calculate memory buffer based on available memory and given ratio
    if the buffer isn't specified, otherwise return the buffer.
    """
    unit_map = {"gb": 1024 ** 3, "mb": 1024 ** 2, "kb": 1024 ** 1, "b": 1024 ** 0}
    if not memory_buffer:
        available_memory = psutil.virtual_memory().available / unit_map[unit]
        memory_buffer = available_memory * ratio
    return float(memory_buffer)


def parse_bool_env(env_name: str, default: bool):
    value = os.getenv(env_name, str(default)).lower()
    if value in ["true"]:
        return True
    else:
        return False


def reindex_test_dataset(query: dict = None, from_index: Optional[str] = None, hex_size=20) -> str:
    """
    Reindexes the master test dataset into isolated pieces.
    :param from_index: Index from which to reindex.
    :param query: Query you want to limit the reindex to.
    :param hex_size: How many random characters should there be in the new indexes name.
    :return: Name of the newly generated index.
    """
    from toolkit.elastic.tools.core import ElasticCore
    from toolkit.test_settings import TEST_INDEX

    from_index = from_index if from_index else TEST_INDEX

    ec = ElasticCore()
    new_test_index_name = f"ttk_test_{uuid.uuid4().hex[:hex_size]}"
    ec.create_index(index=new_test_index_name)
    ec.add_texta_facts_mapping(new_test_index_name)

    from_scan = elasticsearch_dsl.Search() if query is None else elasticsearch_dsl.Search.from_dict(query)
    from_scan = from_scan.index(from_index).using(ec.es)
    from_scan = from_scan.scan()


    def doc_actions(generator):
        for document in generator:
            yield {
                "_index": new_test_index_name,
                "_type": "_doc",
                "_source": document.to_dict(),
                "retry_on_conflict": 3
            }


    actions = doc_actions(from_scan)
    from elasticsearch.helpers import bulk
    bulk(actions=actions, client=ec.es, refresh="wait_for")
    return new_test_index_name


def wrap_in_list(item):
    if isinstance(item, list):
        return item
    else:
        return [item]


def prepare_mandatory_directories(*directories):
    for directory_path in directories:
        path = pathlib.Path(directory_path)
        if not path.exists():
            path.mkdir(parents=True, exist_ok=True)
