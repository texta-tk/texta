$('input[name="file"]').val('');
$('#keep-synchronized').val('false');
$('#remove-existing-dataset').val('false');
// $('.apply-preprocessor').val([]);

// $('#input-type').change(function () {
//     $(".input-type-pane").hide();
//     $("#" + $(this).val()).show();
// });
//
// $('#file-content').change(function () {
//     $(".file-content-pane").hide();
//     $("#" + $(this).val()).show();
// });
//
// $('#single-file-format').change(function () {
//     $(".single-file-format-pane").hide();
//     $("#" + $(this).val()).show();
// });
//
// $('#collection-file-format').change(function () {
//     $(".collection-file-format-pane").hide();
//     $("#" + $(this).val()).show();
// });
//
// $('#database-type').change(function () {
//     $(".database-type-pane").hide();
//     $("#" + $(this).val()).show();
// });

// $('#import-dataset-btn').click(function() {
//     importDataset();
// });
$('#import-dataset-form').on('submit',(function(){
    validateForm();
    importDataset();
}));

function importDataset() {
    /**
     * Format: file extension
     */

    var formData = new FormData();
    formData = collectFormats(formData);
    formData = collectTextaDatasetArguments(formData);
    formData = collectDataArguments(formData);
    // formData = collectPreprocessorArguments(formData);

    var isImporting = false;

    $.ajax({
        url: 'import',
        data: formData,
        type: 'POST',
        contentType: false,
        processData: false,
        beforeSend: function() {
            loaderDisplay("beforeSend");
            isImporting = true;
        },
        success: function() {
            $('#jobs-table-div').load('reload_table');
            loaderDisplay("success");
            isImporting = false;
        },
        error: function() {
            $('#jobs-table-div').load('reload_table');
            loaderDisplay("error")
            isImporting = false;
        }
    });

    if (isImporting) {
        var refreshId = setInterval(function(){
            if (!isImporting) {
                clearInterval(refreshId);
            }
            $('#jobs-table-div').load('reload_table');
        }, 5000);
    }
}

function removeImportJob(id) {
    $.ajax({
        url: 'remove_import_job',
        data: {'id': id},
        type: 'POST',
        success: function() {
            $('#jobs-table-div').load('reload_table');
        }
    })
}





$('.file-input-method-btn').on('click',(function() {
    $('.file-input-method-btn').removeClass('selected');
    $(this).addClass('selected');
    $('.file-input-method').hide();
    $('#' + $(this).val() + '-file-input').show();

    fileInputSelection($(this).val());
}));

// $('.apply-preprocessor').on('click',(function() {
//     var preprocessorIdx = $(this).data('preprocessorIdx');
//     if (this.checked) {
//         $('#preprocessor-' + preprocessorIdx + '-parameters').slideDown()
//     } else {
//         $('#preprocessor-' + preprocessorIdx + '-parameters').slideUp()
//     }
// }));

$('#data-formats').on('change',(function() {
    var parameterTags = getSelectedFormatsParameterTags(this);
    displayFormatsParameters(parameterTags);
    displaySelectedFormatsNames(this);
}));

function getSelectedFormatsParameterTags(selectTag) {
    var checkedFormats = $(selectTag).find('option:checked');
    var parameterTags = new Set();

    checkedFormats.each(function() {
        var formatTags = $(this).data('parametersTags').split(',');
        for (var i = 0; i < formatTags.length; i++) {
            parameterTags.add(formatTags[i]);
        }
    });

    return parameterTags;
}

function displaySelectedFormatsNames(selectTag) {
    var checkedFormats = $(selectTag).find('option:checked');
    var parameterNames = [];

    checkedFormats.each(function() {
        parameterNames.push($(this).text());
    });

    $('#selected-data-formats-list').html(parameterNames.join(', '));

    return parameterNames;
}

function displayFormatsParameters(parameterTags) {
    $('.format-parameters').removeClass('relevant-parameters');

    for (var it = parameterTags.values(), tag= null; tag=it.next().value; ) {
        $('#' + tag + '-format-parameters').addClass('relevant-parameters');
    }
}