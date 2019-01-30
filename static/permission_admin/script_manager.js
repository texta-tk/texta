
$("#new-project-files").on('change',(function() {
    var fileInput = document.getElementById('new-project-files');
    var fileNames = [];
    for (var i = 0; i < fileInput.files.length; ++i) {
        fileNames.push(fileInput.files.item(i).name);
    }

    setOptions(fileNames);
}))

$(document).on('click', '.delete-btn', function() {
    var listItem = $(this).parent().parent().parent()
    var projectId = listItem.data('id');

    $.ajax({
        url: LINK_PERMISSION_ADMIN+'/delete_script_project',
        type: 'POST',
        data: {'project_id': projectId},
        success: function() {
            listItem.remove();
        }
    });
    event.preventDefault();
})

$(document).on('click', '.run-btn', function(event) {
    var listItem = $(this).parent().parent().parent()
    var projectId = listItem.data('id');

    $.ajax({
        url: LINK_PERMISSION_ADMIN+'/run_script_project',
        type: 'POST',
        data: {'project_id': projectId},
        success: function() {

        }
    });
    event.preventDefault();
});

$(document).on('click', '.list-group-item', function() {
    var projectId = $(this).data('id')
})

function setOptions(optionNames) {
    var select = document.getElementById('new-project-entrance');

    select.innerHTML = "";

    for (var i = 0; i < optionNames.length; i++){
        var option = document.createElement('option');
        option.value = optionNames[i];
        option.innerHTML = optionNames[i];
        select.appendChild(option);
    }

}

function getProjectList() {
    $("#project-list").load(LINK_PERMISSION_ADMIN+'/project_list')
}


$('#add-project-form').on('submit',(function(event) {
    event.preventDefault();
    var $form = $( this ),
    url = $form.attr( 'action' );

    var formData = new FormData(document.getElementById('add-project-form'))

    //$.post(url, formData, getProjectList)

    $.ajax({
        url: url,
        data: formData,
        processData: false,
        contentType: false,
        type: 'POST',
        success: function(data){
            getProjectList();
        }
});

}))

$('#new-project-btn').on('click',(getProjectList))

getProjectList()
