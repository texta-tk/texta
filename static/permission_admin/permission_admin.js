/**
 * Created by katrin on 19.11.15.
 */

 
$(document).ready(function() {
	$('#daterange_from').datepicker({format: "yyyy-mm-dd",startView:2});
	$('#daterange_to').datepicker({format: "yyyy-mm-dd",startView:2});
}); 
 
$('#index').on('change', function() {
    console.log('jipii');
    var mapping_selection = $('#mapping');
    mapping_selection.html('');
    $.getJSON(LINK_ROOT+'permission_admin/get_mappings',{index:$(this).val()}, function(mappings) {
        console.log(mappings)
        for (var i=0; i < mappings.length; i++) {
            var mapping = mappings[i];
            $('<option></option').val(mapping).text(mapping).appendTo(mapping_selection);
        }
    });
});

$('#index').trigger('change');

function delete_user(username){
    var delete_user = confirm('Delete user '.concat(username).concat('?'));
    console.log(delete_user);
    if(delete_user === true){
        $.post(LINK_ROOT+'permission_admin/delete_user', {username: username}, function(){
            location.reload();
        });
    }
}

function add_dataset(){
	var index = $('#index').val();
	var mapping = $('#mapping').val();
	var daterange_from = $('#daterange_from').val();
	var daterange_to = $('#daterange_to').val();
    $.post(LINK_ROOT+'permission_admin/add_dataset', {index: index, mapping: mapping, daterange_from: daterange_from, daterange_to: daterange_to}, function(){
        location.reload();
    });	
}

function remove_index(index){
    var delete_index = confirm('Remove?');
    console.log(remove_index);
    if(delete_index === true){
        $.post(LINK_ROOT+'permission_admin/delete_dataset', {index: index}, function(){
            location.reload();
        });
    }
}

function open_close_dataset(dataset_id,open_close){
    $.post(LINK_ROOT+'permission_admin/open_close_dataset', {dataset_id: dataset_id, open_close: open_close}, function(){
        location.reload();
    });	
}