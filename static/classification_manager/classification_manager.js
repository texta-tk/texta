
function train_classifier(){

        var search = $('#search').val();
		var field = $('#field').val();
		var extractor_opt = $('#extractor_opt').val();
        var reductor_opt = $('#reductor_opt').val();
        var normalizer_opt = $('#normalizer_opt').val();
        var classifier_opt = $('#classifier_opt').val();
		var description = $('#description').val();

		if(search.length > 0 && field.length > 0){

			$.post(LINK_CLASSIFICATION_MANAGER + "/start_training_job",
                {
                    search:search,
                    field: field,
                    extractor_opt: extractor_opt,
                    reductor_opt: reductor_opt,
                    normalizer_opt: normalizer_opt,
                    classifier_opt: classifier_opt,
                    description:description
                },
                function(data){
				    window.location.replace(LINK_CLASSIFICATION_MANAGER);
			    });

		}else{
			alert('Parameters not set!');
		}
}


function confirm_and_remove(model_id) {
    if (confirm('Are you sure you want to delete the model ID '+model_id+' ?')) {
        window.location = LINK_CLASSIFICATION_MANAGER + '/delete_model?model_id=' + model_id;
    }
}
