$('select').val('');
$('input[name="file"]').val('');
$('#keep_synchronized').val('false');
$('.apply-preprocessor').val([]);

$('#input-type').change(function () {
    $(".input-type-pane").hide();
    $("#" + $(this).val()).show();
});

$('#file-content').change(function () {
    $(".file-content-pane").hide();
    $("#" + $(this).val()).show();
});

$('#single-file-format').change(function () {
    $(".single-file-format-pane").hide();
    $("#" + $(this).val()).show();
});

$('#collection-file-format').change(function () {
    $(".collection-file-format-pane").hide();
    $("#" + $(this).val()).show();
});

$('#database-type').change(function () {
    $(".database-type-pane").hide();
    $("#" + $(this).val()).show();
});

function importDataset(format) {
    /**
     * Format: file extension
     */

    var form = $('#' + format + '-parameters')[0];
    var formData = new FormData(form);
    var type = $('#input-type').val();
    if (type === 'file') {
        var archiveFormat = $('#archive-format').val();
        if (archiveFormat !== 'no-archive') {
            formData.append('archive', archiveFormat);
        }
    }

    var keepSynchronized = $('#keep_synchronized').val();
    formData.append('keep_synchronized', keepSynchronized);

    $.ajax({
        url: 'import',
        data: formData,
        type: 'POST',
        contentType: false,
        processData: false,
        success: function() {
            $('#jobs-table-div').load('reload_table');
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
    console.log(parameterTags);

    for (var it = parameterTags.values(), tag= null; tag=it.next().value; ) {
        $('#' + tag + '-format-parameters').addClass('relevant-parameters');
    }
}