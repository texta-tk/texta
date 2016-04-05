var selected_checkboxes = new Array();

var PREFIX = LINK_MODEL_MANAGER;

function tick(checkbox_id){
	index_of = $.inArray(checkbox_id, selected_checkboxes)
	if(index_of != -1) {
		selected_checkboxes.splice(index_of,1);
	}else{
		selected_checkboxes.push(checkbox_id);
	}
}

function train_model(){
		var description = $('#description').val();
		var num_dimensions = $('#num_dimensions').val();
		var num_workers = $('#num_workers').val();
		var min_freq = $('#min_freq').val();
		var search = $('#search').val();
		var field = $('#field').val();
		if(search.length > 0 && field.length > 0){
			$.post(PREFIX + "/start_training_job", {field:field,
													num_dimensions:num_dimensions,
													num_workers:num_workers,
													min_freq:min_freq,
													search:search,
													description:description,
													lexicon_reduction:selected_checkboxes}, function(data){
				alert('The training job has begun. Check the models table for updates.');
				window.location.replace(LINK_MODEL_MANAGER);
			});
		}else{
			alert('Parameters not set!');
		}
}