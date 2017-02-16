var PREFIX = LINK_DOCUMENT_MINER;


$(document).ready(function() {
    get_searches();
});


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
	
	

    var request = new XMLHttpRequest();

    var formElement = document.getElementById("filters");
    
    request.onreadystatechange=function() {
        if (request.readyState==4 && request.status==200) {

			$('#suggestions').html(request.responseText);
			$('body').css('cursor', 'auto');

        }
    }
    
    request.open("POST",PREFIX+'/query');
    request.send(new FormData(formElement),true);	
	
}


function accept_document(id){
	$('#docs').val($('#docs').val()+'\n'+id);
	$('#row_'+id).remove();
}

function decline_document(id){
	var declined_as_list = JSON.parse($('#docs_declined').val());
	declined_as_list.push(id);
	$('#docs_declined').val(JSON.stringify(declined_as_list));
	$('#row_'+id).remove();
}




//FOR HANDLING TEXTA SEARCH LISTINGS
//COPIED FROM SEARCHER

function get_searches() {
    var request = new XMLHttpRequest();

    var formElement = document.getElementById("filters");
    
    request.onreadystatechange=function() {
        if (request.readyState==4 && request.status==200) {
            if (request.responseText.length > 0) {
                display_searches(JSON.parse(request.responseText));
            }
        }
    }
    
    request.open("GET",PREFIX+'/listing');
    request.send(new FormData(formElement),true);
}

function remove_search_callback(response_text) {
    var search_div = document.getElementById("search_"+response_text);
    search_div.parentNode.removeChild(search_div);
}

function display_searches(searches) {
    var searches_container = document.getElementById("saved_searches");
	
    while (searches_container.firstChild) {
        searches_container.removeChild(searches_container.firstChild);
    }
	
    for (var i = 0; i < searches.length; i++) {
		search_div = document.createElement("tr");

		inputElement = document.createElement("input");
        aElement = document.createElement("span");
        
        search_div.id = "search_" + searches[i].id;
        
        inputElement.type = "checkbox";
        inputElement.name = "saved_search_" + i;
        inputElement.value = searches[i].id;
        
		aElement.className = "glyphicon glyphicon-minus-sign pointer";
        aElement.onclick = function(id) {
            return function() {async_get_query(PREFIX + "/corpus_tool/delete?pk=" + id,remove_search_callback); };
        }(searches[i].id);      
		
		input_col = document.createElement("td");
		input_col.appendChild(inputElement);   
        search_div.appendChild(input_col);

		text_col = document.createElement("td");
		text_col.appendChild(document.createTextNode(searches[i].desc));
        search_div.appendChild(text_col);

		remove_col = document.createElement("td");
		remove_col.appendChild(aElement);   
        search_div.appendChild(remove_col);

        searches_container.appendChild(search_div);
    }
}