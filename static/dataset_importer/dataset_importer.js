$('select').val('');

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