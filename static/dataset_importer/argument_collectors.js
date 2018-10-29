
// Data format collector

function collectFormats(formData) {
    var checkedFormats = $('#data-formats').find('option:checked');
    var formatValues = [];

    checkedFormats.each(function() {
        formatValues.push($(this).val());
    });

    formData.append('formats', JSON.stringify(formatValues));

    return formData;
}

// Input data collectors

function collectDataArguments(formData) {
    var tags = getSelectedFormatsParameterTags($('#data-formats'));

    for (var it = tags.values(), tag= null; tag=it.next().value; ) {
        formData = collectors[tag](formData);
    }

    return formData;
}

function collectFileLikeArguments(formData) {
    var selectedInputMethod = $('.file-input-method-btn.selected').val();
    var fileInput = $('#' + selectedInputMethod + '-file-input input');

    if (selectedInputMethod === 'upload') {
        formData.append('file', fileInput[0].files[0]);
    } else {
        formData.append(selectedInputMethod, fileInput.val());
    }

    return formData;
}

function collectBdocArguments(formData) {
    formData.append('bdoc_password', $('#bdoc-password').val())
    return formData
}

function collectHtmlArguments(formData) {
    return formData;
}

function collectXmlArguments(formData) {
    return formData;
}

function collectElasticArguments(formData) {
    return formData;
}

function collectMongoDbArguments(formData) {
    return formData;
}

function collectSqliteArguments(formData) {
    return formData;
}

function collectPostgresArguments(formData) {
    return formData;
}

// TEXTA dataset collector

function collectTextaDatasetArguments(formData) {
    var datasetName = $('#texta-elastic-dataset-name').val();
    var notAnalyzedFieldsRawValue = $('#texta-elastic-not-analyzed').val();

    if (notAnalyzedFieldsRawValue === "") {
        var notAnalyzedFields = JSON.stringify([]);
    } else {
        var notAnalyzedFields = notAnalyzedFieldsRawValue.split('\n');
    }

    var keepSynchronized = $('#keep-synchronized').val();
    var removeExistingDataset = $('#remove-existing-dataset').val();

    formData.append('texta_elastic_index', datasetName);
    formData.append('texta_elastic_mapping', datasetName);
    formData.append('texta_elastic_not_analyzed', notAnalyzedFields);
    formData.append('keep_synchronized', keepSynchronized);
    formData.append('remove_existing_dataset', removeExistingDataset);

    return formData;
}

// Preprocessor collectors

function collectPreprocessorArguments(formData) {
    var appliedPreprocessors = [];

    $('.apply-preprocessor:checked').each(function() {
        formData = collectors[$(this).val()](formData);
        appliedPreprocessors.push($(this).val())
    });

    formData.append('preprocessors', JSON.stringify(appliedPreprocessors));

    return formData;
}

function collectMlpArguments(formData) {
    var featureNames = JSON.stringify($('#mlp-processor-feature-names').val().split('\n'));

    formData.append('mlp_preprocessor_feature_names', featureNames);

    return formData;
}

function collectDateConverterArguments(formData) {
    var featureNames = JSON.stringify($('#date-converter-processor-feature-names').val().split('\n'));
	  var featureLangs = JSON.stringify($('#date-converter-processor-feature-langs').val().split('\n'));

    formData.append('date_converter_preprocessor_feature_names', featureNames);
	  formData.append('date_converter_preprocessor_input_langs',featureLangs);

    return formData;
}

function collectTextTaggerArguments(formData) {
    var featureNames = JSON.stringify($('#text-tagger-processor-feature-names').val().split('\n'));
    var taggers = JSON.stringify($('#text-tagger-processor-taggers').val());

    formData.append('text_tagger_preprocessor_feature_names', featureNames);
    formData.append('text_tagger_preprocessor_taggers', taggers);

    return formData;
}

function collectLexiconTaggerArguments(formData) {
    var featureNames = JSON.stringify($('#lexicon-classifier-processor-feature-names').val().split('\n'));
	  var lexicons = JSON.stringify($('#lexicon-classifier-processor-lexicons').val().split('\n'));
    var match_type = JSON.stringify($('#lexicon-classifier-processor-match-types').val());
	  var operation = JSON.stringify($('#lexicon-classifier-processor-operations').val());
    var slop = JSON.stringify($('#lexicon-classifier-processor-slops').val());
	  var requiredWords = JSON.stringify($('#lexicon-classifier-processor-words-required').val());
    var addCounterLexicon = JSON.stringify($('#lexicon-classifier-processor-add-cl').val());
    var counterLexicons = JSON.stringify($('#lexicon-classifier-processor-counterlexicons').val());
    var clSlop = JSON.stringify($('#lexicon-classifier-processor-cl-slops').val());

    formData.append('lexicon_classifier_preprocessor_feature_names', featureName);
	  formData.append('lexicon_classifier_preprocessor_lexicons', lexicons);
    formData.append('lexicon_classifier_preprocessor_match_types', match_type);
    formData.append('lexicon_classifier_preprocessor_operations', operation);
    formData.append('lexicon_classifier_preprocessor_slops', slop);
    formData.append('lexicon_classifier_preprocessor_words_required', requiredWords);
    formData.append('lexicon_classifier_preprocessor_counterlecixons', counterLexicons);
    formData.append('lexicon_classifier_preprocessor_cl_slops', clSlop);
    formData.append('lexicon_classifier_preprocessor_add_cl', addCounterLexicon);
    
    return formData;
}

// Key to collector map

var collectors = {
    formats: collectFormats,
    textaDataset: collectTextaDatasetArguments,

    file: collectFileLikeArguments,
    html: collectHtmlArguments,
    xml: collectXmlArguments,
    elastic: collectElasticArguments,
    mongodb: collectMongoDbArguments,
    sqlite: collectSqliteArguments,
    postgres: collectPostgresArguments,

    mlp: collectMlpArguments,
	  date_converter: collectDateConverterArguments,
	  text_tagger: collectTextTaggerArguments,
    lexicon_coverter: collectLexiconTaggerArguments
};
