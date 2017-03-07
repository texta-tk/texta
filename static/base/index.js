$('#lex_miner').click(function() {
    window.location = LINK_LEXMINER;
})

$('#corpus_tool').click(function() {
    window.location = LINK_CORPUS_TOOL;
})

$('#mwe_miner').click(function() {
    window.location = LINK_MWE;
})

$('#home').click(function() {
    window.location = LINK_ROOT;
})

$('#conceptualizer').click(function() {
    window.location = LINK_CONCEPTUALISER;
})

$('#model_manager').click(function() {
    window.location = LINK_MODEL_MANAGER;
})

$('#ontology_viewer').click(function() {
    window.location = LINK_ONTOLOGY_VIEWER;
})

$('#permission_admin').click(function() {
    window.location = LINK_PERMISSION_ADMIN;
})

$('#grammar_builder').click(function() {
    window.location = LINK_GRAMMAR_BUILDER;
})

$('#notRegistered').click(function() {
    $(this).hide()
    $('#registrationForm').slideDown(1000);
})

$('#cancelRegistrationBtn').click(function() {
    $('#registrationForm').slideUp(1000, function() {
        $('#notRegistered').slideDown(300);
    });
    clearRegistrationForm();
})

$('#registrationForm > .form-group > .form-control').focus(function() {
    validateInput($(this).attr('id'));
})

function registerAccount() {

    var usernameInput = $("#registrationUsername");
    var passwordInput = $("#registrationPassword");
    var passwordAgainInput = $("#registrationPasswordAgain");
    var emailInput = $("#registrationEmail");
    
    var failed = false;
    
    if (passwordInput.val() != passwordAgainInput.val()) {
        invalidateInput("registrationPasswordAgain","has-error","Passwords don't match.")
        return;
    }
    
    $.post(LINK_ACCOUNT+'/create', {username:usernameInput.val(), password:passwordInput.val(), email:emailInput.val()}, function(data){
        if (data.url == "#") {
            //console.log(data.issues.username[0]);
            if (data.issues && data.issues.username) {
                invalidateInput("registrationUsername","has-error","Username exists or is too short.");
            }
        } else {
            go_to(data.url);
        }
    }, "json");
    
}

function invalidateInput(input_id, status, message) {
    var input = $("#"+input_id);
    var parent = input.parent();
    var helpBlock = parent.find(".help-block")
    if (helpBlock.length) {
        helpBlock.text(message);
    } else {
        var spanElement = document.createElement('span');
        spanElement.className = 'help-block';
        spanElement.appendChild(document.createTextNode(message));
        $(spanElement).appendTo(parent);
    }
    parent.removeClass("has-success has-warning has-error");
    parent.addClass(status);
    
    return input
}

function validateInput(input_id) {
    var input = $("#"+input_id);
    var parent = input.parent();
    parent.removeClass("has-success has-warning has-error");
    parent.find(".help-block").remove();
    
    return input
}

function clearRegistrationForm() {
    var ids = ['registrationUsername','registrationPassword','registrationPasswordAgain','registrationEmail'];
    
    for (var i = 0 ; i < ids.length ; i++) {
        validateInput(ids[i]).val("");
    }
}