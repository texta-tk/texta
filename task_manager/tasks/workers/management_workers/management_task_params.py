from enum import Enum, unique

# Enum for management sub-workers, must have unique values
@unique
class ManagerKeys(str, Enum):
    FACT_DELETER = "fact_deleter"
    FACT_ADDER = "fact_adder"
