var LINK_PREFIX = 'http://localhost:8000';
var STATIC_URL = 'http://localhost:8000/static/'

var LINK_LEXMINER = LINK_PREFIX + '/lexicon_miner';
var LINK_SEARCHER = LINK_PREFIX + '/searcher';
var LINK_MWE = LINK_PREFIX + '/mwe_miner';
var LINK_ROOT = LINK_PREFIX + '/';
var LINK_CONCEPTUALISER = LINK_PREFIX + '/conceptualiser';
var LINK_ACCOUNT = LINK_PREFIX + '/account';
var LINK_MODEL_MANAGER = LINK_PREFIX + '/model_manager';
var LINK_CLASSIFICATION_MANAGER = LINK_PREFIX + '/classification_manager';
var LINK_ONTOLOGY_VIEWER = LINK_PREFIX + '/ontology_viewer';
var LINK_PERMISSION_ADMIN = LINK_PREFIX + '/permission_admin';
var LINK_GRAMMAR_BUILDER = LINK_PREFIX + '/grammar_builder';
var LINK_DOCUMENT_MINER = LINK_PREFIX + '/document_miner';
var LINK_DATASET_IMPORTER = LINK_PREFIX + '/dataset_importer';
var LINK_TASK_MANAGER = LINK_PREFIX + '/task_manager';


function go_to(link,form_id) {
    if(form_id) {
	document.getElementById(form_id).action = link;
    } else {
	window.location = link;
    }
	
}

function async_get_query(link,callback_function) {
    var xhr = new XMLHttpRequest();

    xhr.onreadystatechange=function() {
        if (xhr.readyState==4 && xhr.status==200) {
            if (callback_function) {
                callback_function(xhr.responseText);
            }
            $('body').css('cursor', 'auto');
        }
    }
    
    xhr.open("GET",link,true);
    $('body').css('cursor', 'wait');
    xhr.send(); 
}
