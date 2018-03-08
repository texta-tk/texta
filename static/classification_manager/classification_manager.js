
function train_classifier(){

        var search = $('#search').val();
		var field = $('#field').val();
		var extractor_opt = $('#extractor_opt').val();
        var reductor_opt = $('#reductor_opt').val();
        var normalizer_opt = $('#normalizer_opt').val();
        var classifier_opt = $('#classifier_opt').val();
        var tag_label = $('#tag_label').val();
		var description = $('#description').val();

		if(search.length > 0 && field.length > 0){

			$.post(LINK_CLASSIFICATION_MANAGER + "/start_training_job",
                {
                    search: search,
                    field: field,
                    extractor_opt: extractor_opt,
                    reductor_opt: reductor_opt,
                    normalizer_opt: normalizer_opt,
                    classifier_opt: classifier_opt,
                    tag_label: tag_label,
                    description: description
                },
                function(data){
				    window.location.replace(LINK_CLASSIFICATION_MANAGER);
			    });

		}else{
			alert('Parameters not set!');
		}
}


function confirm_and_remove(model_id){
    if (confirm('Are you sure you want to delete the model ID '+model_id+' ?')) {
        window.location = LINK_CLASSIFICATION_MANAGER + '/delete_model?model_id=' + model_id;
    }
}


function display_summary_modal(train_summary,tag){

    $("#information_modal_content").html(JSON.stringify(JSON.parse(train_summary),null,2));
    $("#information_modal_title").html('Training summary for tag: <i>'+tag+'</i>');

    $("#information_modal").modal('show');
}


function display_key_modal(key,tag){

    $("#information_modal_content").html(key);
    $("#information_modal_title").html('Key for tag: <i>'+tag+'</i>');

    $("#information_modal").modal('show');
}


function display_arch_modal(arch,tag){

    $("#information_modal_content").html(arch);
    $("#information_modal_title").html('Architecture for tag: <i>'+tag+'</i>');

    $("#information_modal").modal('show');
}


function display_apply_modal(model_id,model_key,tag_label){
    $("#apply_model_id").val(model_id);
    $("#apply_model_key").val(model_key);
    $("#selected_tag_label").html(tag_label);

    $("#apply_modal").modal('show');

}


function apply_model(){
    var model_id = $("#apply_model_id").val();
    var model_key = $("#apply_model_key").val();
    var apply_on_search = $("#apply_search").val();

    if(apply_on_search.length > 0){
        $.post(LINK_CLASSIFICATION_MANAGER + "/apply_model",{model_id: model_id, model_key: model_key, search: apply_on_search},
            function(data){
	        window.location.replace(LINK_CLASSIFICATION_MANAGER);
            }
        );
    }else{
        alert('Search not selected!');
    }

}
