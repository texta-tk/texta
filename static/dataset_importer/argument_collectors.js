
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

    if (selectedInputMethod === 'file') {
        formData.append('file', fileInput[0].files[0]);
    } else {
        formData.append(selectedInputMethod, fileInput.val());
    }

    return formData;
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
    var notAnalyzedFields = JSON.stringify($('#texta-elastic-not-analyzed').val().split('\n'));
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

    formData.append('mlp_preprocessor_input_features', featureNames);

    return formData;
}


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

    mlp: collectMlpArguments
};