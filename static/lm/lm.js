var positive_to_sid = {};
var name_to_punct = {'___r_para___': ')', '___exclamation___': '!', '___slash___': '/', '___comma___': ',', '___period___': '.', '___question___': '?', '___question___': ' ', '___backslash___': '\\', '___semicolon___': ';', '___quot___': '"', '___r_bracket___': ']', '___colon___': ':', '___l_bracket___': '[', '___hyphen___': '-', '___apo___': "'", '___l_para___': '(', '___space___': ' ', '___and___' : '&', '___percentage___': '%'};
var PREFIX = LINK_LEXMINER;

$(document).ready(function(){
	$("#new_lexicon_button").click(function(){
		$("#inputDiv").slideToggle("slow",function(){});
    });

    $('#lx-'+ $('.selectedText').attr('id')).css({ 'font-weight': 'bold', 'color':'#333'});
});

function getParam(sParam){
	var sPageURL = window.location.search.substring(1);
	var sURLVariables = sPageURL.split('&');
	for (var i = 0; i < sURLVariables.length; i++){
		var sParameterName = sURLVariables[i].split('=');
		if (sParameterName[0] == sParam){
			return sParameterName[1];
		}
	}
}

function addWord(word){
	positive_to_sid[word]=parseInt($('#sid').val());
	$('#suggestion_' + word).remove();
	for (var name in name_to_punct) {
	    word = word.replace(name,name_to_punct[name]);
	}
	$('#lexicon').val($('#lexicon').val()+'\n'+word);
}

function query(){
    var negatives = [];
    //$('#suggestions').children().filter('div').each(function() {negatives.push($(this).text().substring(2))});
    $('#suggestion_cell_1').children().filter('div').each(function() {negatives.push($(this).text().substring(2))});
    $('#suggestion_cell_2').children().filter('div').each(function() {negatives.push($(this).text().substring(2))});
    
    sid = $('#sid').length == 1 ? $("#sid").val() : -1;

    selected_text = $('#lexicon').textrange().text
    content = selected_text.length > 0 ? selected_text : $('#lexicon').val();

    $('body').css('cursor', 'wait');

    $.post(PREFIX + "/query", {content: content,lid: $('#lid').val(),method: $('#method').val(),negatives: JSON.stringify(negatives),sid: sid,tooltip_feature: $('#tooltip-feature').val()}, function(data){
	    if (data.length == 0) {

			swal({
				    title: 'Oops. Something went wrong.',
				    text: 'No suggestions... Do you have the language model trained?',
				    type: 'warning',
				    confirmButtonColor: '#73AD21',
				    cancelButtonColor: '#d33',
				    confirmButtonText: 'Ok'
		
			}).then((result) => {})	

        } else {

		    $('#suggestions').html(data);
			$('body').css('cursor', 'auto');
        
        }
    });
}

function save() {
    var xmlhttp = new XMLHttpRequest();
    xmlhttp.onreadystatechange=function() {
	if (xmlhttp.readyState==4 && xmlhttp.status==200) {
	    $('body').css('cursor', 'auto');
	}
    }

    var form_data = new FormData();
    //form_data.append("lexicon",$("#lexicon").val());
    form_data.append("id",$("#lid").val());
    var lexicon = [];
    var lexicon_words = $("#lexicon").val().split("\n");
    for (var i = 0; i < lexicon_words.length; i++) {
	var lexicon_word = lexicon_words[i];
	if (lexicon_word.length > 0) {
	    lexicon.push({word:lexicon_word,sid: lexicon_word in positive_to_sid ? positive_to_sid[lexicon_word] : -1})
	}
    }
    form_data.append("lexicon",JSON.stringify(lexicon));

    xmlhttp.open("POST",PREFIX + "/save",false);
    $('body').css('cursor', 'wait');
    xmlhttp.send(form_data);
    
}

function reset_suggestions() {
    var xhr = new XMLHttpRequest();
    
    xhr.onreadystatechange=function() {
	if (xhr.readyState==4 && xhr.status==200) {
	    $('body').css('cursor', 'auto');
	}
    }
    
    var form_data = new FormData();
    form_data.append("lid",$("#lid").val());
    xhr.open("POST",PREFIX + "/reset_suggestions",false);
    $('body').css('cursor', 'wait');
    xhr.send(form_data);
}
