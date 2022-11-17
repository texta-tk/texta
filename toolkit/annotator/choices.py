from enum import Enum


class AnnotationType(Enum):
    BINARY = "binary"
    MULTILABEL = "multilabel"
    ENTITY = "entity"

MAX_VALUE = 10000
ANNOTATION_CHOICES = [(a.value, a.value) for a in AnnotationType]
