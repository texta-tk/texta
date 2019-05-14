var PREFIX = LINK_ROOT

var MAX_DESC_LEN = 20

$(document).ready(function () {
    $('#model option').each(function () {
        var option = $(this)
        var short_text = prune(option.text(), MAX_DESC_LEN)
        if (option.text().length > short_text.length) {
            option.text(short_text + '...')
        }
    })
})

function change_pwd () {
    var pwd = $('#new_password').val()
    var pwd_2x = $('#confirm_new_password').val()

    if (pwd == pwd_2x && pwd.length > 0) {
        var data = { new_password: pwd }

        $.post(LINK_ROOT + '/change_password', data, function (data) {
            swal({
                title: 'Updated!',
                text: 'Password updated!',
                type: 'success',
                heightAuto: false
		        }).then((result) => { location.reload() })
        })
    } else {
        swal({
            title: 'Warning!', text: 'Passwords do not match or fields empty!', type: 'warning', heightAuto: false })
    }
}

function prune (s, symbols_left) {
    return s.substring(0, symbols_left)
}
