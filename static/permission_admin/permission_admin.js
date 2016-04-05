/**
 * Created by katrin on 19.11.15.
 */

 
$(document).ready(function() {
	$('#daterange_from').datepicker({format: "yyyy-mm-dd",startView:2});
	$('#daterange_to').datepicker({format: "yyyy-mm-dd",startView:2});
}); 
 
function delete_user(username){
    var delete_user = confirm('Delete user '.concat(username).concat('?'));
    console.log(delete_user);
    if(delete_user === true){
        $.post('/permission_admin/delete_user', {username: username}, function(){
            location.reload();
        });
    }
}

function add_dataset(){
	var index = $('#index').val();
	var mapping = $('#mapping').val();
	var daterange_from = $('#daterange_from').val();
	var daterange_to = $('#daterange_to').val();
    $.post('/permission_admin/add_dataset', {index: index, mapping: mapping, daterange_from: daterange_from, daterange_to: daterange_to}, function(){
        location.reload();
    });	
}

function remove_index(index){
    var delete_index = confirm('Remove?');
    console.log(remove_index);
    if(delete_index === true){
        $.post('/permission_admin/delete_dataset', {index: index}, function(){
            location.reload();
        });
    }
}