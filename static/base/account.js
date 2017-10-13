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

function change_pwd(){	
	var pwd = $("#new_password").val();
	var pwd_2x = $("#confirm_new_password").val();
	
	if(pwd == pwd_2x && pwd.length>0){
		$("#change_password").attr('action',PREFIX+'change_password');
		$("#change_password").attr('target','_self');
		$("#change_password").submit();	
	}else{
		alert('Passwords do not match or fields empty!');
	}
}

function prune(s,symbols_left) {
    return s.substring(0,symbols_left);
}