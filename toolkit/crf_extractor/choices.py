from texta_crf_extractor.feature_extraction import DEFAULT_LAYERS, DEFAULT_EXTRACTORS

FEATURE_FIELDS_CHOICES = list((a, a) for a in DEFAULT_LAYERS)
FEATURE_EXTRACTOR_CHOICES = list((a, a) for a in DEFAULT_EXTRACTORS)
