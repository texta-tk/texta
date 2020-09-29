import regex as re
from rest_framework.exceptions import ValidationError

def validate_patterns(lexicon):
    invalid_patterns = []
    for pattern in lexicon:
        try:
            re.compile(pattern)
        except Exception as e:
            invalid_patterns.append({"pattern": pattern, "error": str(e)})
    if invalid_patterns:
        raise ValidationError(f"Invalid regex pattern(s): {invalid_patterns}")
