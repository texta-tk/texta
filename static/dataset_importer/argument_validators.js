function loaderDisplay(status) {
    if (status == "beforeSend") {
        $("#loader").show();
        $("#loader").fadeIn("slow");
        $("#import-dataset-btn").prop('disabled', true);
        $("#import-dataset-btn").html('Importing');

        $(".statusText").hide();
    }
    else if (status == "success") {
        $("#loader").fadeOut("slow");
        $("#loader").hide();
        $("#import-dataset-btn").prop('disabled', false);
        $("#import-dataset-btn").html('Import');

        $(".statusText").html("Successfully started import job!");
        $(".statusText").css("color", "#73AD21");
        $(".statusText").show();
    }
    else if (status == "error") {
        $("#loader").fadeOut("slow");
        $("#loader").hide();
        $("#import-dataset-btn").prop('disabled', false);
        $("#import-dataset-btn").html('Import');

        $(".statusText").html("Error starting import job!");
        $(".statusText").css("color", "red");
        $(".statusText").show();
    }
}

var fileInputFormats = [['HTML', "PDF", "DOCX", "RTF", "TXT", "DOC"], ["XML", "JSON", "CSV", "XLS/XLSX"], ["SQLite"], ['Elasticsearch', 'MongoDB', 'Elasticsearch, MongoDB', 'MongoDB, Elasticsearch']];

//last validation steps when pressing import
function validateForm() {
    //validate other formats when elastic/mongodb were selected
    if (fileInputFormats[0].concat(fileInputFormats[1].concat(fileInputFormats[2])).some(element => $('#selected-data-formats-list').text().includes(element))) {
        $('#' + $('.file-input-method-btn.selected').val() + '-file-input-field').prop('required', true);
    } else {
        $('.file-input-field').prop('required', false);
    }
}
//for fileinput validation
function fileInputSelection(active) {
    $('#import-dataset-btn').prop('disabled', false);
    $('.file-input-field').prop('required', false);
    $('#' + active + '-file-input-field').prop('required', true);
}

//when preprocessor changed
$("#apply-preprocessor").on('change',(function () {
    if (this.checked) {
        $("#mlp-processor-feature-names").prop('required', true);
        if (fileInputFormats[0].some(element => $('#selected-data-formats-list').text().includes(element))) {
            $("#mlp-processor-feature-names").html('text');
        }
    } else {
        $("#mlp-processor-feature-names").prop('required', false);
    }
}));

//when data formats text changed
$("#selected-data-formats-list").bind("DOMSubtreeModified", function () {
    //for mlp validation
    if (fileInputFormats[0].some(element => $('#selected-data-formats-list').text().includes(element))) {
        $("#mlp-processor-feature-names").html('text');
    } else {
        $("#mlp-processor-feature-names").html('');
    }
    //for elastic/mongodb validation
    if (fileInputFormats[3].some(element => $('#selected-data-formats-list').text() == element)) {
        $('#import-dataset-btn').prop('disabled', false);
        $('.file-input-field').prop('required', false);
    } else if ($('#selected-data-formats-list').text() != '' && typeof ($('.file-input-method-btn.selected').val()) === 'undefined') {
        $('#import-dataset-btn').prop('disabled', true);
    }
});