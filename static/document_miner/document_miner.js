var PREFIX = LINK_DOCUMENT_MINER;

function query(){

    $('body').css('cursor', 'wait');
	
	var new_rejected = [];
		$('[not_yet_accepted]').each(function() {
		  var value = $(this).attr('not_yet_accepted');
		  new_rejected.push(value);
	});
		
	rejected = $('#docs_declined').val();
	
	if(rejected.length > 0){
		rejected = JSON.parse(rejected);
		rejected = rejected.concat(new_rejected);
	}else{
		rejected = new_rejected;
	}
	
	rejected = JSON.stringify(rejected);
	
	$('#docs_declined').val(rejected);
	
    $.post(PREFIX + "/query", {
			field: $('#field').val(),
			docs: $('#docs').val(), 
			docs_declined: $('#docs_declined').val(),
			handle_negatives: $('#handle_negatives').val(),
			must_not: $('#must_not').val(),
			stopwords: $('#stopwords').val()
		},
		function(data){
			$('#suggestions').html(data);
			$('body').css('cursor', 'auto');
		}
	);
}


function accept_document(id){
	$('#docs').val($('#docs').val()+'\n'+id);
	$('#row_'+id).remove();
}

function decline_document(id){
	if($('#declined').val().length > 0){
		var addition = '\n'+id;
	}else{
		var addition = id;
	}
	$('#declined').val($('#declined').val()+addition);
	$('#row_'+id).remove();
}