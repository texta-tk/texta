var PREFIX = LINK_TASK_MANAGER;

$(function () {
    // for bootstrap 3 use 'shown.bs.tab', for bootstrap 2 use 'shown' in the next line
    $('a[data-toggle="tab"]').each(function () {
        $(this).on('shown.bs.tab', function (e) {
            // save the latest tab; use cookies if you like 'em better:
            localStorage.setItem('lastTab', $(this).attr('href'));
        });
    });

    // go to the latest tab, if it exists:
    let lastTab = localStorage.getItem('lastTab');
    if (lastTab) {
        $('[href="' + lastTab + '"]').tab('show');
    }
});


function start_task(task_id) {
    let formElement = document.getElementById("task_params");
    $("<input>").attr("type", "hidden").attr("name", "task_type").val(task_id).appendTo(formElement);

    let request = new XMLHttpRequest();
    request.onreadystatechange = function () {
        location.reload();

    };

    request.open("POST", PREFIX + '/start_task');
    request.send(new FormData(formElement));

}


function select_preprocessor(task_id) {
    let preprocessor_key = $("#" + task_id + "_preprocessor_key").val();
    $("[id^=params-]").addClass('hidden');
    $("#params-" + preprocessor_key).removeClass('hidden');
}


function delete_task(task_id) {
    let data = {task_id: task_id};

    swal({
        title: 'Are you sure?',
        text: 'This will remove the task and it\'s resources.',
        type: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#73AD21',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Yes, delete!'

    }).then((result) => {

        if (result.value) {
            $.post(PREFIX + '/delete_task', data, function (data) {
                location.reload();
            });
        }
    })

}
