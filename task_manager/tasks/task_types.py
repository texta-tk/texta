from enum import Enum, unique

# Enum for task type keys, must have unique values
@unique
class TaskTypes(str, Enum):
    TRAIN_MODEL = "train_model"
    TRAIN_TAGGER = "train_tagger"
    TRAIN_ENTITY_EXTRACTOR = "train_entity_extractor"
    APPLY_PREPROCESSOR = "apply_preprocessor"
    MANAGEMENT_TASK = "management_task"
