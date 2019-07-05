import json
import logging

from texta.settings import ERROR_LOGGER
from utils.mlp_task_adapter import MLPTaskAdapter
from utils.mlp_task_adapter import Helpers


class MLPLitePreprocessor(object):
    """
    Cleans texts for classification. Lemmatizes text.
    """

    def _reload_env(self):
        import dotenv
        dotenv.load_dotenv(".env")


    def __init__(self, mlp_url=None):
        self.mlp_url = mlp_url
        self._reload_env()


    @staticmethod
    def _process_stats(stats):
        """ Processes stats from TextCleaner to make them categorical
        """
        processed_stats = {}
        if stats:
            for stat_key, stat_val in stats.items():
                if isinstance(stat_val, list) and stat_key == 'obfuscated':
                    if stat_val:
                        processed_stats[stat_key] = 'obfuscated'
                    else:
                        processed_stats[stat_key] = 'not_obfuscated'
                if isinstance(stat_val, list):
                    processed_stats[stat_key] = ' '.join(stat_val)
                elif isinstance(stat_val, float):
                    processed_stats[stat_key] = str(stat_val).replace('.', '_')
                elif isinstance(stat_val, int):
                    processed_stats[stat_key] = str(len(str(stat_val)))
                else:
                    processed_stats[stat_key] = stat_val

        return processed_stats


    def transform(self, documents, **kwargs):
        """Takes input documents and creates new fields for further commentary analysis.
        :param documents: collection of dictionaries to enhance
        :param kwargs: request parameters which must include entries for the preprocessors to work appropriately
        :type documents: list of dicts
        :return: enhanced documents
        :rtype: list of dicts
        """

        # this is mostly for API requests as they might not have field data - apply to all in this case
        feature_names = kwargs.get('mlp-lite_feature_names', None)
        output_type = kwargs.get('mlp-lite_output_type', None)

        input_features = json.loads(feature_names) if feature_names else list(documents[0].keys())
        output_type = json.loads(kwargs['mlp-lite_output_type']) if output_type else 'full'

        for input_feature in input_features:

            try:
                input_feature = json.loads(input_features)["path"]
            except:
                pass

            input_feature_path = input_feature.split(".")

            # Nested field or a normal field?
            if len(input_feature_path) > 1:
                texts = [Helpers.traverse_nested_dict_by_keys(document, input_feature_path) for document in documents]
            else:
                texts = [document[input_feature] if input_feature in document else "" for document in documents]

            data = {'texts': json.dumps(texts, ensure_ascii=False)}
            analyzation_data, errors = MLPTaskAdapter(self.mlp_url, mlp_type='mlp_lite').process(data)

            for analyzation_idx, analyzation_datum in enumerate(analyzation_data):
                # Because for some whatever reason, at times this will be None
                # If it happens, ignore it, log it, and move on with life.
                try:
                    # Is it a nested field or a normal field?
                    if len(input_feature_path) > 1:
                        # Make sure the last field is used as the path.
                        mlp_field_path = input_feature_path[:-1] + [input_feature_path[-1] + "_mlp-lite"]
                        Helpers.set_in_dict(documents[analyzation_idx], mlp_field_path, {})

                        mlp_text_path = mlp_field_path + ["text"]
                        Helpers.set_in_dict(documents[analyzation_idx], mlp_text_path, analyzation_datum['text'])

                        if output_type == 'full':
                            mlp_stats_path = mlp_field_path + ["stats"]
                            Helpers.set_in_dict(documents[analyzation_idx], mlp_stats_path, self._process_stats(analyzation_datum["stats"]))

                    else:
                        documents[analyzation_idx][input_feature + '_mlp-lite'] = {}
                        documents[analyzation_idx][input_feature + '_mlp-lite']['text'] = analyzation_datum['text']
                        if output_type == 'full':
                            documents[analyzation_idx][input_feature + '_mlp-lite']['stats'] = self._process_stats(analyzation_datum['stats'])
                except Exception as e:
                    logging.getLogger(ERROR_LOGGER).exception("Error Message: {}, Document: {}".format(e, documents[analyzation_idx]))
                    continue

        return {'documents': documents, 'meta': {}, 'erros': errors}
