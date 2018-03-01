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

        $(".statusText").html("Successfully imported database!");
        $(".statusText").css("color", "#73AD21")
        $(".statusText").show();
    }
    else if (status == "error") {
        $("#loader").fadeOut("slow");
        $("#loader").hide();
        $("#import-dataset-btn").prop('disabled', false);
        $("#import-dataset-btn").html('Import');

        $(".statusText").html("Error importing database!");
        $(".statusText").css("color", "red")
        $(".statusText").show();
    }
}

function fileInputSelection() {
    $('#import-dataset-btn').prop('disabled', false);
    $('.file-input-field').prop('required', false);
    $('#' + $(this).val() + '-file-input-field').prop('required', true);
}

$("#apply-preprocessor").change(function () {
    if (this.checked) {
        $("#mlp-processor-feature-names").prop('required', true);
        if (['HTML', "PDF", "DOCX", "RTF", "TXT", "DOC"].some(element => $('#selected-data-formats-list').text().includes(element))) {
            $("#mlp-processor-feature-names").html('text');
        }
    } else {
        $("#mlp-processor-feature-names").prop('required', false);
    }
});


$("#selected-data-formats-list").bind("DOMSubtreeModified", function () {
    if (['HTML', "PDF", "DOCX", "RTF", "TXT", "DOC"].some(element => $('#selected-data-formats-list').text().includes(element))) {
        $("#mlp-processor-feature-names").html('text');
    } else {
        $("#mlp-processor-feature-names").html('');
    }
});