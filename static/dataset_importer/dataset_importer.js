$('select').val('');
$('input[name="file"]').val('');
$('#keep-synchronized').val('false');
$('#remove-existing-dataset').val('false');
$('.apply-preprocessor').val([]);

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
function loaderDisplay(beforeSend) {
    if(beforeSend){
        $("#loaderDiv").show();
        $("#loader").fadeIn("slow");
        $("#import-dataset-btn").prop('disabled', true);
        $("#import-dataset-btn").html('Importing');
        
    }
    else {
        $("#loader").fadeOut("slow");
        $("#loaderDiv").hide();
        $("#import-dataset-btn").prop('disabled', false);
        $("#import-dataset-btn").html('Import');
    }
}

$('#import-dataset-btn').click(function() {
    importDataset();
});

function importDataset() {
    /**
     * Format: file extension
     */

    var formData = new FormData();
    formData = collectFormats(formData);
    formData = collectTextaDatasetArguments(formData);
    formData = collectDataArguments(formData);
    formData = collectPreprocessorArguments(formData);

    $.ajax({
        url: 'import',
        data: formData,
        type: 'POST',
        contentType: false,
        processData: false,
        beforeSend: function() {
            loaderDisplay(true);
        },
        success: function() {
            $('#jobs-table-div').load('reload_table');
            loaderDisplay(false);
        }
    });
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





$('.file-input-method-btn').click(function() {
    $('.file-input-method-btn').removeClass('selected');
    $(this).addClass('selected');
    $('.file-input-method').hide();
    $('#' + $(this).val() + '-file-input').show();
});

$('.apply-preprocessor').click(function() {
    var preprocessorIdx = $(this).data('preprocessorIdx');
    if (this.checked) {
        $('#preprocessor-' + preprocessorIdx + '-parameters').slideDown()
    } else {
        $('#preprocessor-' + preprocessorIdx + '-parameters').slideUp()
    }
});

$('#data-formats').change(function() {
    var parameterTags = getSelectedFormatsParameterTags(this);
    displayFormatsParameters(parameterTags);
});

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

function displayFormatsParameters(parameterTags) {
    $('.format-parameters').removeClass('relevant-parameters');

    for (var it = parameterTags.values(), tag= null; tag=it.next().value; ) {
        $('#' + tag + '-format-parameters').addClass('relevant-parameters');
    }
}