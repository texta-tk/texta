var selected = new Array();
var selected_2 = new Array();

var PREFIX = LINK_MWE;

function start_job(){
	if(selected.length == 0){
		swal('Warning!','No lexicons selected!','warning');
	}else{
		var slop = $('#slop').val();
		var max_len = $('#max_len').val();
		var min_len = $('#min_len').val();
		var min_freq = $('#min_freq').val();
		var match_field = $('#match_field').val();
		var description = $('#description').val();

		swal({
			title: "The mapping job has begun.",
			text: "Check the results table for updates.",
			type: "success",
			showCancelButton: false,
			confirmButtonColor: "#73AD21",
			confirmButtonText: "Continue"
			}).then((result) => {
				$.post(PREFIX + "/start_mapping_job", {lexicons:selected,max_len:max_len,min_len:min_len,min_freq:min_freq,match_field:match_field,slop:slop,description:description}, function(data){
					window.location.replace(LINK_MWE);
				});
		});
	}
}

function select_lexicon(lexicon_id){
	index_of = $.inArray(lexicon_id, selected)
	if(index_of != -1) {
		selected.splice(index_of,1);
	}else{
		selected.push(lexicon_id);
	}
}

function tick_term(parent,child){
	var parent_box_id = '#concept_'+parent.toString();
	index_of = $.inArray(child, selected_2)
	if(index_of != -1) {
		selected_2.splice(index_of,1);
	}else{
		selected_2.push(child);
	}
}

function tick_concept(parent,children){
	var parent_box_id = '#concept_'+parent.toString();
	if($(parent_box_id).prop('checked') == true){
		$.each(children, function(key,child) {
			$('#term_'+child.toString()).prop('checked', true);
			index_of = $.inArray(child, selected_2)
			if(index_of == -1) {
				selected_2.push(child);
			}	
		});
	}else{
		$.each(children, function(key,child) {
			$('#term_'+child.toString()).prop('checked', false);
			index_of = $.inArray(child, selected_2)
			if(index_of != -1) {
				selected_2.splice(index_of,1);
			}				
		});	
	}
}

function toggle_group(a){
	var group_id = '#group_'+a.toString();
	  $(group_id).toggle();
}

function apply_changes(){
	var op = $('#operator').val();
	if(op == 'reverse' && selected_2.length == 0){
		swal('Warning!','No terms selected!','warning');
	}else{
		var run_id = $('#run_id').val();
		$.post(PREFIX + "/approve", {approved:selected_2,operator:op,run_id:run_id}, function(data){
			window.location.reload();
		});	
	}
}
