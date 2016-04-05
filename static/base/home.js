var PREFIX = LINK_ROOT;

var MAX_DESC_LEN = 20;

$(document).ready(function() {
    $("#model option").each(function() {
        var option = $(this);
		var short_text = prune(option.text(),MAX_DESC_LEN)
		if(option.text().length > short_text.length){
			option.text(short_text+'...');
		}
    });
})

function update(){
	$("#settings").attr('action',PREFIX+'update');
	$("#settings").attr('target','_self');
	$("#settings").submit();
return true;}

function prune(s,symbols_left) {
    return s.substring(0,symbols_left);
}