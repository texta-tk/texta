from texta_tagger.tools.mlp_analyzer import get_mlp_analyzer
from toolkit.settings import MLP_URL, MLP_MAJOR_VERSION

# initiate global instance for MLP Analyzer
mlp_analyzer = get_mlp_analyzer(MLP_URL, MLP_MAJOR_VERSION)
