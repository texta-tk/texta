from typing import List
from rest_framework.exceptions import ValidationError
from toolkit.elastic.core import ElasticCore


def check_if_in_elastic(indices: List[str]):
    ec = ElasticCore()
    if indices:
        is_in_index = ec.check_if_indices_exist(indices=indices)
        if is_in_index is False:
            raise ValidationError(f"Indices in {str(indices)} do not match with indices available in Elasticsearch!")
