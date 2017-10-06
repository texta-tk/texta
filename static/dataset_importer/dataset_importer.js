$('select').val('')

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