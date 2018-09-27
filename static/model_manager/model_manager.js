var selected_checkboxes = [];
var PREFIX = LINK_MODEL_MANAGER;

function tick(checkbox_id) {
    let index_of = $.inArray(checkbox_id, selected_checkboxes);
    if (index_of !== -1) {
        selected_checkboxes.splice(index_of, 1);
    } else {
        selected_checkboxes.push(checkbox_id);
    }
}

function train_model() {
    let description = $('#description').val();
    let num_dimensions = $('#num_dimensions').val();
    let num_workers = $('#num_workers').val();
    let min_freq = $('#min_freq').val();
    let search = $('#search').val();
    let field = $('#field').val();

    if (search.length > 0 && field.length > 0) {

        $.post(PREFIX + "/start_training_job", {
            field: field,
            num_dimensions: num_dimensions,
            num_workers: num_workers,
            min_freq: min_freq,
            search: search,
            description: description,
            lexicon_reduction: selected_checkboxes
        });

        swal({
            title: "The mapping job has begun.",
            text: "Check the results table for updates.",
            type: "success",
            showCancelButton: false,
            confirmButtonColor: "#73AD21",
            confirmButtonText: "Continue"
        }).then(function () {
            window.location.replace(LINK_MODEL_MANAGER);
        });
    } else {
        swal('Warning!', 'Parameters not set!', 'warning');
    }
}


