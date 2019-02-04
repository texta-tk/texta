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

function start_task_management(task_id ,formElement,managerKey){
    formElement = document.getElementById(formElement)
    $('<input>').attr('type', 'hidden').attr('name', 'task_type').val(task_id).appendTo(formElement)
    $('<input>').attr('type', 'hidden').attr('name', 'manager_key').val(managerKey).appendTo(formElement)
    $('<input>').attr('type', 'hidden').attr('name', 'description').val($('#management-task-description-param').val()).appendTo(formElement)
    // $('<input>').attr('type', 'hidden').attr('name', 'search').val($('#management-task-search-param').val()).appendTo(formElement)

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

function select_manager (task_id) {
    let manager_key = $('#' + task_id + '_manager_key').val()
    $('[id^=params-]').addClass('hidden')
    $('#params-' + manager_key).removeClass('hidden')
}

function deleteDocuments (type) {
    let task_ids = []
    $('input[name="dt_'+type+'_delete"]').each(function() {
        if ($( this ).is(":checked")) {
            task_ids.push($(this).attr('id'))
        }
    });

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
            $.ajax({
                url: PREFIX+'/delete_task',
                data: {'task_ids[]': task_ids},
                type: 'POST',
                success: function(result) {
                    if(result.error){
                        swalCustomTypeDisplay(SwalType.ERROR, result.error)
                    }else{
                        location.reload()
                    }

                }
            })
        }
    })

}

function downloadModel(model_id_to_download) {
    window.location.href = `${LINK_TASK_MANAGER}/download_model?model_id=${model_id_to_download}`
}

function togglePanelCollapse(element) {
    $(element).children('.glyphicon').toggleClass('glyphicon-plus')
    $(element).children('.glyphicon').toggleClass('glyphicon-minus')
}

function uploadTask(task_form_id) {
    formElement = document.getElementById(task_form_id)
    formData = new FormData(formElement);
    
    statusTextElem = $('#uploadStatus')
    $.ajax({
        url: PREFIX + '/upload_task_archive',
        data: formData,
        type: 'POST',
        contentType: false,
        processData: false,
        beforeSend: function () {
            statusTextElem.get(0).textContent = "Importing, please wait.."
            statusTextElem.attr('class', 'taskUploadStatusTextDefault')
        },
        success: function (data) {
            status = data.status
            switch (status) {
                case 'success':
                    statusTextElem.get(0).textContent = data.text
                    statusTextElem.attr('class', 'taskUploadStatusTextSuccess')
                    break
                case 'failed':
                    statusTextElem.get(0).textContent = data.text
                    statusTextElem.attr('class', 'taskUploadStatusTextFailed')
                    break
                default:
                    statusTextElem.get(0).textContent = "An unknown error has occurred, make sure the exported Task data is valid and try again."
                    statusTextElem.attr('class', 'taskUploadStatusTextFailed')
                    break
            }
        },
        error: function () {
            statusTextElem.get(0).textContent = "An unknown error has occurred, make sure the exported Task data is valid and try again."
            statusTextElem.attr('class', 'taskUploadStatusTextFailed')
        }
    });
}