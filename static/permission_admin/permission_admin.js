$(document).ready(function () {
    $('a[data-toggle="tab"]').on('shown.bs.tab', function (e) {
        localStorage.setItem('permissionAdminLastTab', $(this).attr('href'))
    })
    let lastTab = localStorage.getItem('permissionAdminLastTab')
    if (lastTab) {
        $('[href="' + lastTab + '"]').tab('show')
    } else {
        let element = $('.top-nav-tabs li').first().children()
        /* element.toggleClass('active') */
        element.tab('show')
    }
    $('#daterange_from').datepicker({
        format: "yyyy-mm-dd",
        startView: 2
    });
    $('#daterange_to').datepicker({
        format: "yyyy-mm-dd",
        startView: 2
    });
});

$('#index').on('change', function () {
    var mapping_selection = $('#mapping');
    mapping_selection.html('');
    $.getJSON(LINK_ROOT + 'permission_admin/get_mappings', {
        index: $(this).val()
    }, function (mappings) {
        for (var i = 0; i < mappings.length; i++) {
            var mapping = mappings[i];
            $('<option></option').val(mapping).text(mapping).appendTo(mapping_selection);
        }
    });
});


$('#index').trigger('change');

function change_is_active(user_id, change) {
    $.post(LINK_ROOT + 'permission_admin/change_isactive', {
        user_id: user_id,
        change: change
    }, function () {
        location.reload();
    });
}

function change_permissions(user_id, change) {
    $.post(LINK_ROOT + 'permission_admin/change_permissions', {
        user_id: user_id,
        change: change
    }, function () {
        location.reload();
    });
}

function delete_user(username, user_id) {
    swal({
        title: 'Are you sure?',
        text: 'Delete user '.concat(username).concat('?'),
        type: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#73AD21',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Yes'
    }).then((result) => {
        if (result.value) {
            swal({
                title: 'Deleted!',
                text: 'User '.concat(username).concat(' has been deleted.'),
                type: 'success'
            }).then((result) => {
                if (result.value) {
                    $.post(LINK_ROOT + 'permission_admin/delete_user', {
                        user_id: user_id
                    }, function () {
                        location.reload();
                    });
                } else {
                    $.post(LINK_ROOT + 'permission_admin/delete_user', {
                        user_id: user_id
                    }, function () {
                        location.reload();
                    });
                }
            })
        }
    })
}

function add_dataset() {
    var index = $('.grid-i-dataset>.index').val();
    var mapping = $('.grid-i-mapping>.mapping').val();
    var daterange_from = $('#daterange_from').val();
    var daterange_to = $('#daterange_to').val();
    var access = $('#access').val();
    $.post(LINK_ROOT + 'permission_admin/add_dataset', {
        index: index,
        mapping: mapping,
        daterange_from: daterange_from,
        daterange_to: daterange_to,
        access: access
    }, function () {
        location.reload();
    });
}

function toggle_wildcard_dataset() {
    $(".grid-i-dataset>.index-input").toggleClass("index"); 
    $(".grid-i-dataset>.wildcard-index-input").toggleClass("index");

    $(".grid-i-mapping>.mapping-input").toggleClass("mapping"); 
    $(".grid-i-mapping>.wildcard-mapping-input").toggleClass("mapping");

    $(".grid-i-mapping>.mapping-input").toggleClass("hidden");
    $(".grid-i-mapping>.wildcard-mapping-input").toggleClass("hidden");

    $(".grid-i-dataset>.index-input").toggleClass("hidden");
    $(".grid-i-dataset>.wildcard-index-input").toggleClass("hidden");
}

function remove_index(index) {
    swal({
        title: 'Are you sure?',
        text: 'Remove?',
        type: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#73AD21',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Yes'
    }).then((result) => {
        if (result.value) {
            swal({
                title: 'Removed!',
                text: 'Dataset removed!',
                type: 'success'
            }).then((result) => {
                if (result.value) {
                    $.post(LINK_ROOT + 'permission_admin/delete_dataset', {
                        index: index
                    }, function () {
                        location.reload();
                    });
                } else {
                    $.post(LINK_ROOT + 'permission_admin/delete_dataset', {
                        index: index
                    }, function () {
                        location.reload();
                    });
                }
            })
        }
    })
}

function delete_index(index) {
    swal({
        title: 'Are you sure?',
        text: 'Delete index?',
        type: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#73AD21',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Yes'
    }).then((result) => {
        if (result.value) {
            swal({
                title: 'Deleted!',
                text: 'Index deleted!',
                type: 'success'
            }).then((result) => {
                if (result.value) {
                    $.post(LINK_ROOT + 'permission_admin/delete_index', {
                        index: index
                    }, function () {
                        location.reload();
                    });
                } else {
                    $.post(LINK_ROOT + 'permission_admin/delete_index', {
                        index: index
                    }, function () {
                        location.reload();
                    });
                }
            })
        }
    })
}


function open_close_dataset(dataset_id, open_close) {
    $.post(LINK_ROOT + 'permission_admin/open_close_dataset', {
        dataset_id: dataset_id,
        open_close: open_close
    }, function () {
        location.reload();
    });
}


function moveItems(origin, destination) {
    $(origin).find(':selected').appendTo(destination)
}

$('.allow-btn').on('click',(function (obj) {
    var userid = $(this).data('userid');
    moveItems('#' + userid + '-disallowed-datasets', '#' + userid + '-allowed-datasets')
}));

$('.disallow-btn').on('click',(function () {
    var userid = $(this).data('userid');
    moveItems('#' + userid + '-allowed-datasets', '#' + userid + '-disallowed-datasets')
}));

function update_dataset_permissions(userId) {
    var allowedDatasets = []
    var disallowedDatasets = []

    var allowedOptions = document.getElementById(userId + '-allowed-datasets').options;
    for (var i = 0; i < allowedOptions.length; i++) {
        allowedDatasets.push(allowedOptions[i].value)
    }

    var disallowedOptions = document.getElementById(userId + '-disallowed-datasets').options;
    for (var i = 0; i < disallowedOptions.length; i++) {
        disallowedDatasets.push(disallowedOptions[i].value)
    }

    $.post(LINK_ROOT + 'permission_admin/update_dataset_permissions', {
            allowed: JSON.stringify(allowedDatasets),
            disallowed: JSON.stringify(disallowedDatasets),
            user_id: userId
        },
        function () {
            location.reload();
        });
}