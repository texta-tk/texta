var PREFIX = LINK_TASK_MANAGER;

function start_task(task_id) {
    var formElement = document.getElementById("task_params");
    $("<input>").attr("type", "hidden").attr("name", "task_type").val(task_id).appendTo(formElement);
    
    var request = new XMLHttpRequest();
    request.onreadystatechange=function() {
        if (request.readyState==4 && request.status==200) {
            if (request.responseText.length > 0) {
            	location.reload();
            }
        }
    }
    request.open("POST",PREFIX+'/start_task');
    request.send(new FormData(formElement),true);

}

function select_preprocessor(task_id) {
    var preprocessor_key = $("#"+task_id+"_preprocessor_key").val();  
    $("[id^=params-]").addClass('hidden'); 
    $("#params-"+preprocessor_key).removeClass('hidden');
}

function delete_task(task_id) {
	var data = {task_id: task_id}

    swal({
            title: 'Are you sure?',
            text: 'This will remove the task and it\'s resources.',
            type: 'warning',
            showCancelButton: true,
            confirmButtonColor: '#73AD21',
            cancelButtonColor: '#d33',
            confirmButtonText: 'Yes, delete!'
    
    }).then((result) => {
       
        if(result.value) {
			$.post(PREFIX+'/delete_task', data, function(data) {
				location.reload();
			});       
        }
    })	

}
