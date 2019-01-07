/* global LINK_TASK_MANAGER */
var PREFIX = LINK_TASK_MANAGER

$(function () {
    $('a[data-toggle="tab"]').on('shown.bs.tab', function (e) {
        $('.data-table:visible').each(function (e) {
            $($.fn.dataTable.tables(true)).DataTable().columns.adjust().responsive.recalc()
        })
        localStorage.setItem('lastTab', $(this).attr('href'))
    })
    /* inits all datatables */
    $('.data-table').DataTable({
        'paging': false,
        'ordering': false,
        'info': false,
        'searching': false,
        responsive: {
            details: true
        }
    })
    /* dont show non datatables version */
    $('.tasks-table').toggleClass('hidden')

    // go to the latest tab, if it exists:
    let lastTab = localStorage.getItem('lastTab')
    if (lastTab) {
        $('[href="' + lastTab + '"]').tab('show')
    } else {
        let element = $('.flex-row.nav.nav-tabs li').first().children()
        element.tab('show')
    }
})
function start_task_preprocessor(task_id ,formElement,preprocessorKey){
    formElement = document.getElementById(formElement)
    $('<input>').attr('type', 'hidden').attr('name', 'task_type').val(task_id).appendTo(formElement)
    $('<input>').attr('type', 'hidden').attr('name', 'preprocessor_key').val(preprocessorKey).appendTo(formElement)
    $('<input>').attr('type', 'hidden').attr('name', 'description').val($('#apply-preprocessor-description-param').val()).appendTo(formElement)
    $('<input>').attr('type', 'hidden').attr('name', 'search').val($('#apply-preprocessor-search-param').val()).appendTo(formElement)

    var request = new XMLHttpRequest()
    request.onreadystatechange = function () {
        location.reload()
    }

    request.open('POST', PREFIX + '/start_task')
    request.send(new FormData(formElement), true)

}

function start_task (task_id, formElement) {

    formElement = document.getElementById(formElement)
    $('<input>').attr('type', 'hidden').attr('name', 'task_type').val(task_id).appendTo(formElement)

    var request = new XMLHttpRequest()
    request.onreadystatechange = function () {
        location.reload()
    }

    request.open('POST', PREFIX + '/start_task')
    request.send(new FormData(formElement), true)
}

function select_preprocessor (task_id) {
    let preprocessor_key = $('#' + task_id + '_preprocessor_key').val()
    $('[id^=params-]').addClass('hidden')
    $('#params-' + preprocessor_key).removeClass('hidden')
}

function delete_task (task_id) {
    let data = {
        task_id: task_id
    }

    swal({
        title: 'Are you sure?',
        text: 'This will remove the task and it\'s resources.',
        type: 'warning',
        heightAuto: false,
        showCancelButton: true,
        confirmButtonColor: '#73AD21',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Yes, delete!'

    }).then((result) => {
        if (result.value) {
            $.post(PREFIX + '/delete_task', data, function (data) {
                location.reload()
            })
        }
    })
}
