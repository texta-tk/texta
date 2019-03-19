from enum import Enum, unique

# TODO use enum values as choices in task_type field 
# https://docs.djangoproject.com/en/2.1/ref/models/fields/#choices

# Enum for task type keys, must have unique values
@unique
class TaskTypes(str, Enum):
    TRAIN_MODEL = "train_model"
    TRAIN_TAGGER = "train_tagger"
    NEUROCLASSIFIER = "neuroclassifier"
    TRAIN_ENTITY_EXTRACTOR = "train_entity_extractor"
    APPLY_PREPROCESSOR = "apply_preprocessor"
    MANAGEMENT_TASK = "management_task"

    @classmethod
    def hasValue(cls, item):
        return item in cls._value2member_map_
