var counter = 1;
var PREFIX = LINK_CORPUS_TOOL;

var examplesTable;

var layers = ['text','lemmas','facts'];

$(document).ready(function() {
    get_searches();
	
	change_agg_field(1);
 
    $(document.body).on( 'click','a.toggle-visibility', function (e) {
        e.preventDefault();
 
        $(this).toggleClass('feature-invisible');
        
        // Get the column API object
        var column = examplesTable.column( $(this).attr('data-column') );
 
        // Toggle the visibility
        column.visible( ! column.visible() );
        
        examplesTable.columns.adjust();
        
        var dataset = $("#dataset").val();
        var mapping = $("#mapping").val();
        
        var hiddenFeatures = localStorage.getCacheItem("hiddenFeatures_"+dataset+"_"+mapping);
        if (!hiddenFeatures) {
            hiddenFeatures = {}
        }

        if ($(this).hasClass('feature-invisible')) {
            hiddenFeatures[$(this).attr('data-column')] = true;
        } else {
            if (hiddenFeatures.hasOwnProperty($(this).attr('data-column'))) {
                delete hiddenFeatures[$(this).attr('data-column')];
            }
        }
        localStorage.setCacheItem(("hiddenFeatures_"+dataset+"_"+mapping), hiddenFeatures, {months: 1});
    } );
});


$(document).mousemove(function(e) {
    window.MOUSE_X = e.pageX;
    window.MOUSE_Y = e.pageY;
});	


function in_array(value, array) {
  return array.indexOf(value) > -1;
}


function add_field(date_range_min,date_range_max){

	var field = $("#constraint_field").val();

    if( !field ){
        alert('No field selected.');
        return;
    }

    counter++;

    var data = JSON.parse(field);
    var field_path = data.path;
    var field_type = data.type;
    var path_list = data.path.split('.');

	var field_name = path_list[0];
	if(path_list.length > 1){
	    var sub_field = path_list[path_list.length-1];
	    field_name += ' ('+sub_field+')';
    }

    new_id = 'field_'+counter.toString();

    if(field_type == 'date'){
        $("#field_hidden_date").clone().attr('id',new_id).appendTo("#constraints");
        $("#field_"+counter.toString()+" #daterange_field_").attr('id','daterange_field_'+counter.toString()).attr('name','daterange_field_'+counter.toString()).val(field_path);
        $("#field_"+counter.toString()+" #selected_field_").attr('id','selected_field_'+counter.toString()).attr('name','selected_field_'+counter.toString()).html(field_name);
        $("#field_"+counter.toString()+" #remove_link").attr('onclick',"javascript:remove_field('"+new_id+"');");
		
        $("#field_"+counter.toString()+" #daterange_from_").attr('id','daterange_from_'+counter.toString());
        $("#field_"+counter.toString()+" #daterange_from_"+counter.toString()).attr('name','daterange_from_'+counter.toString());
        $("#field_"+counter.toString()+" #daterange_from_"+counter.toString()).datepicker({format: "yyyy-mm-dd",startView:2,startDate:date_range_min,endDate:date_range_max});
        $("#field_"+counter.toString()+" #daterange_to_").attr('id','daterange_to_'+counter.toString());
        $("#field_"+counter.toString()+" #daterange_to_"+counter.toString()).attr('name','daterange_to_'+counter.toString());
        $("#field_"+counter.toString()+" #daterange_to_"+counter.toString()).datepicker({format: "yyyy-mm-dd",startView:2,startDate:date_range_min,endDate:date_range_max});
    }

    else if(field_type == 'facts'){
        $("#field_hidden_fact").clone().attr('id',new_id).appendTo("#constraints");
        $("#field_"+counter.toString()+" #fact_operator_").attr('id','fact_operator_'+counter.toString()).attr('name','fact_operator_'+counter.toString());
        $("#field_"+counter.toString()+" #selected_field_").attr('id','selected_field_'+counter.toString()).html(field_name);
        $("#field_"+counter.toString()+" #fact_field_").attr('id','fact_field_'+counter.toString()).attr('name','fact_field_'+counter.toString()).val(field_path);
        $("#field_"+counter.toString()+" #remove_link").attr('onclick',"javascript:remove_field('"+new_id+"');");
        $("#field_"+counter.toString()+" #suggestions_").attr('id','suggestions_'+counter.toString()).attr('name','suggestions_'+counter.toString());
        $("#field_"+counter.toString()+" #fact_txt_").attr('id','fact_txt_'+counter.toString()).attr('name','fact_txt_'+counter.toString());
        $("#field_"+counter.toString()+" #fact_txt_"+counter.toString()).attr('onkeyup','lookup($(this).val(),'+counter.toString()+',"keyup","'+field_path+'", "FACT");');
        $("#field_"+counter.toString()+" #fact_txt_"+counter.toString()).attr('onfocus','lookup($(this).val(),"'+counter.toString()+'","focus","'+field_path+'", "FACT");');
        $("#field_"+counter.toString()+" #fact_txt_"+counter.toString()).attr('onblur','hide("'+counter.toString()+'");');
    }

    else{
        $("#field_hidden").clone().attr('id',new_id).appendTo("#constraints");
        $("#field_"+counter.toString()+" #match_operator_").attr('id','match_operator_'+counter.toString()).attr('name','match_operator_'+counter.toString());
        $("#field_"+counter.toString()+" #selected_field_").attr('id','selected_field_'+counter.toString()).html(field_name);
        $("#field_"+counter.toString()+" #match_field_").attr('id','match_field_'+counter.toString()).attr('name','match_field_'+counter.toString()).val(field_path);
        $("#field_"+counter.toString()+" #match_type_").attr('id','match_type_'+counter.toString()).attr('name','match_type_'+counter.toString());
        $("#field_"+counter.toString()+" #match_slop_").attr('id','match_slop_'+counter.toString()).attr('name','match_slop_'+counter.toString());
        $("#field_"+counter.toString()+" #remove_link").attr('onclick',"javascript:remove_field('"+new_id+"');");
        $("#field_"+counter.toString()+" #suggestions_").attr('id','suggestions_'+counter.toString()).attr('name','suggestions_'+counter.toString());
        $("#field_"+counter.toString()+" #match_txt_").attr('id','match_txt_'+counter.toString()).attr('name','match_txt_'+counter.toString());
        $("#field_"+counter.toString()+" #match_txt_"+counter.toString()).attr('onkeyup','lookup($(this).val(),'+counter.toString()+',"keyup","'+field_path+'", "TEXT");');
        $("#field_"+counter.toString()+" #match_txt_"+counter.toString()).attr('onfocus','lookup($(this).val(),"'+counter.toString()+'","focus","'+field_path+'", "TEXT");');
        $("#field_"+counter.toString()+" #match_txt_"+counter.toString()).attr('onblur','hide("'+counter.toString()+'");');
    }

    $("#field_"+counter.toString()).show();
    $("#constraint_field").val('');

}

function select_all_fields(){
	if($('#check_all_mapping_fields').prop('checked') == true){
		$.each($("[name^='mapping_field_']"), function () {
			$(this).prop('checked', true);
		});
	}else{
		$.each($("[name^='mapping_field_']"), function () {
			$(this).prop('checked', false);
		});		
	}
}

function hide(id){
	setTimeout(function() {
		$("#field_"+id+" #suggestions_"+id).hide();
	}, 500);
}

function insert(concept_id,field_id,descriptive_term, lookup_type){
	if(concept_id){
		$('#field_'+field_id+" #match_txt_"+field_id).val(function(index, value) {return value.replace(/[^(\n)]*$/, '');});
		$('#field_'+field_id+" #match_txt_"+field_id).val($('#field_'+field_id+" #match_txt_"+field_id).val()+"@"+concept_id+"-"+descriptive_term+"\n");
		$('#field_'+field_id+" #match_txt_"+field_id).focus();
	}else{
	    if(lookup_type == 'TEXT'){
	        $('#field_'+field_id+" #match_txt_"+field_id).val(function(index, value) {return value.replace(/[^(\n)]*$/, '');});
		    $('#field_'+field_id+" #match_txt_"+field_id).val($('#field_'+field_id+" #match_txt_"+field_id).val()+descriptive_term+"\n");
	    }
	    if(lookup_type == 'FACT'){
	        $('#field_'+field_id+" #fact_txt_"+field_id).val(function(index, value) {return value.replace(/[^(\n)]*$/, '');});
		    $('#field_'+field_id+" #fact_txt_"+field_id).val($('#field_'+field_id+" #fact_txt_"+field_id).val()+descriptive_term+"\n");
	    }
	}
}

function remove_field(id){
	$("#"+id).remove();
}

function query(){
    
    var formElement = document.getElementById("filters");
    var request = new XMLHttpRequest();
    
    request.onreadystatechange=function() {
        if (request.readyState==4 && request.status==200) {
            $("#right").html(request.responseText);
            examplesTable = $('#examples').DataTable({
                  "bAutoWidth": false,
                  "deferRender": true,
                  "bServerSide": true,
                  'processing': true,
                  "sAjaxSource": PREFIX+"/table_content",
                  "sDom": '<"H"ipr>t<"F"lp>',
                  "sServerMethod":"POST",
                  "fnServerParams":function(aoData){
                      aoData.push({'name':'filterParams','value':JSON.stringify($("#filters").serializeArray())});
                   },
                  "oLanguage": { "sProcessing": "Loading..."}
            });
            var dataset = $("#dataset").val();
            var mapping = $("#mapping").val();
            loadUserPreference(dataset,mapping);
            $("#actions-btn").removeClass("invisible");
            $("#export-examples-modal").removeClass("invisible");
            $("#export-aggregation-modal").addClass("invisible");
        }
    }

    request.open("POST",PREFIX+'/table_header');
    request.send(new FormData(formElement));    
    
}

function lookup(content,id,action,field_name, lookup_type){
    var lookup_data = {content: content, id: id, action: action, field_name: field_name, lookup_type: lookup_type}
	$.post(PREFIX+'/autocomplete', lookup_data, function(data) {
		if(data.length > 0){
			$("#field_"+id+" #suggestions_"+id).html(data).show();
		}else{
			$("#field_"+id+" #suggestions_"+id).html(data).hide();
		}
	});
}


function aggregate(){
    
    var formElement = document.getElementById("filters");
    var request = new XMLHttpRequest();
    
    request.onreadystatechange=function() {
        if (request.readyState==4 && request.status==200) {
            if (request.responseText.length > 0) {
				displayAgg(JSON.parse(request.responseText));
                $("#actions-btn").removeClass("invisible");
                $("#export-examples-modal").addClass("invisible");
                $("#export-aggregation-modal").removeClass("invisible");
            }
        }
    }

    request.open("POST",PREFIX+'/aggregate');
    request.send(new FormData(formElement),true);
}


function displayAgg(response){
	
	var data = response;
	var container = $("#right");
	container.empty();
	
	$("#popup").empty();
	
	var string_container = $("<div id='string_agg_container'></div>");
	var chart_container = $("<div id='daterange_agg_container'></div>");

	container.append(chart_container);	
	container.append(string_container);
	
	for (var i in data) {
		if(data.hasOwnProperty(i)){
			if(data[i].type == 'daterange'){
				drawTimeline(data[i]);
			}else if(data[i].type == 'string'){
				drawStringAggs(data[i]);
			}
		} 
	}
	
}


function show_children(data) {
	var popup = $("#popup");
	popup.empty();

	$.each(data, function(i,data_list){
		var response_container = $("<div class='bg-grey' style='float: left; padding-left: 20px; padding-right: 20px;'></div>");
		response_container.append("<h2>"+data_list.label+"</h2>");
		$.each(data_list.data, function(j,row){
			var row_container = $("<div class'row'></div>");
			var key_container = $("<div class='col-md-3'>"+row.val+"</div>");
			var val_container = $("<div class='col-md-9'>"+row.key+"</div>");

			row_container.append(key_container);
			row_container.append(val_container);
			response_container.append(row_container);			

		});
		popup.append(response_container);
	});

    popup.fadeIn("fast");
    popup.css("top", MOUSE_Y);
    popup.css("left", MOUSE_X);
	popup.css("position","absolute");
	
}


function show_string_children(data) {
	var popup = $("#popup");
	popup.empty();

	var response_container = $("<div class='bg-grey' style='float: left; padding-left: 20px; padding-right: 20px;'></div>");
//	response_container.append("<h2>"+data_list.label+"</h2>");
			
	$.each(data, function(i,data_list){

		var row_container = $("<div class'row'></div>");
		var key_container = $("<div class='col-md-3'>"+data_list.val+"</div>");
		var val_container = $("<div class='col-md-9'>"+data_list.key+"</div>");

		row_container.append(key_container);
		row_container.append(val_container);
		response_container.append(row_container);			

	});

	popup.append(response_container);
	
    popup.fadeIn("fast");
    popup.css("top", MOUSE_Y);
    popup.css("left", MOUSE_X);
	popup.css("position","absolute");
	
}


function drawTimeline(data){

	new Morris.Line({
		  element: 'daterange_agg_container',
		  resize: true,
		  data: data.data,
		  // The name of the data record attribute that contains x-values.
		  xkey: 'date',
		  // A list of names of data record attributes that contain y-values.
		  ykeys: data.ykeys,
		  // Labels for the ykeys -- will be displayed when you hover over the
		  // chart.
		  labels: data.labels,

		}).on('click', function(i, row) {
			var children_data = data.children[row.date];
			show_children(children_data);
		});

}

function drawStringAggs(data){
	var response_container = $("<div class='panel' style='float: left; padding-left: 20px; padding-right: 20px; min-width: 400px;'></div>");
	response_container.append("<div class='panel-body'><h2>"+data.label+"</h2></div>");
	
	var list_group = $("<ul class='list-group'></ul>");
	
	$.each(data.data, function(i,row){
		var row_container = $("<div class='row'></div>");
		var key_container = $("<div class='col-lg-7 pull-right'>"+row.key+"</div>");
		var val_container = $("<div class='col-lg-5 pull-left'>"+row.val+"</div>");
		
		row_container.append(val_container);
		row_container.append(key_container);

		var li_container = $("<li class='list-group-item'></li>");
		
		if(row.children.length > 0){
			li_container.mouseover(function(){show_string_children(row.children)}).mouseout(function(){$("#popup").hide();});
		}
		
		li_container.append(row_container);
		list_group.append(li_container);
	});
	
	response_container.append(list_group);
	
	$("#string_agg_container").append(response_container);
}


function change_agg_field(field_nr){	
	var field_component = $("#agg_field_"+field_nr);
	var selected_field = field_component.val();
	var selected_type = JSON.parse(selected_field)['type'];
	
	if(selected_type == 'string'){
		$("#sort_by_"+field_nr).removeClass('hidden');
		$("#freq_norm_"+field_nr).addClass('hidden');
		$("#interval_"+field_nr).addClass('hidden');
	}else if (selected_type == 'date'){
		$("#freq_norm_"+field_nr).removeClass('hidden');
		$("#interval_"+field_nr).removeClass('hidden');
		$("#sort_by_"+field_nr).addClass('hidden');		
	}
	
}

function toggle_agg_field_2(action){
	
	if(action == 'add'){
		$("#agg_field_2_container").removeClass('hidden');
		$("#agg_field_2_button").addClass('hidden');
		$("#agg_field_2_selected").val('true');
	}else{
		$("#agg_field_2_button").removeClass('hidden');
		$("#agg_field_2_container").addClass('hidden');
		$("#agg_field_2_selected").val('false');		
	}

	
}

function remove_by_query(){
    var formElement = document.getElementById("filters");
    var request = new XMLHttpRequest();
    
    request.onreadystatechange=function() {
        if (request.readyState==4 && request.status==200) {
            if (request.responseText.length > 0) {
				alert('The documents are being deleted. Check the progress by searching again.');
            }
        }
    }

    request.open("POST",PREFIX+'/remove_by_query');
    request.send(new FormData(formElement),true);	
}


function save(){
	var description = prompt("Enter description for the search.");
	$('#search_description').val(description);
    
    var formElement = document.getElementById("filters");
    var request = new XMLHttpRequest();
    
    request.onreadystatechange=function() {
        if (request.readyState==4 && request.status==200) {
            get_searches();
        }
    }

    request.open("POST",PREFIX+'/save');
    request.send(new FormData(formElement),true);
    
}

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

    var searches_div = document.getElementById("saved_searches");
    while (searches_div.firstChild) {
        searches_div.removeChild(searches_div.firstChild);
    }
        
    for (var i = 0; i < searches.length; i++) {
        search_div = document.createElement("div")
        inputElement = document.createElement("input");
        aElement = document.createElement("a");
        imgElement = document.createElement("img");
        
        search_div.id = "search_" + searches[i].id;
        
        inputElement.type = "checkbox";
        inputElement.name = "saved_search_" + i;
        inputElement.value = searches[i].id;
        
        aElement.href = "javascript:void(0)";
        aElement.onclick = function(id) {
            return function() {async_get_query(PREFIX + "/corpus_tool/delete?pk=" + id,remove_search_callback); };
        }(searches[i].id);
        
        imgElement.src = STATIC_URL + "img/delete.png";
        
        search_div.appendChild(inputElement);
        search_div.appendChild(document.createTextNode(searches[i].desc + "  "));
        
        aElement.appendChild(imgElement);
        
        search_div.appendChild(aElement);
        

        searches_div.appendChild(search_div);
        
    }

}

function loadUserPreference(dataset,mapping) {
    var hiddenFeatures = localStorage.getCacheItem("hiddenFeatures_"+dataset+"_"+mapping);
    
    if (hiddenFeatures) {
        for (var featureIdx in hiddenFeatures) {
            if (hiddenFeatures.hasOwnProperty(featureIdx)) {
                $("#feature-"+featureIdx).trigger("click");
            }
        }
    }
}

function export_data(exportType) {
    var formElement = document.getElementById("filters");
    
    var query_args = $("#filters").serializeArray();
    
    query_args.push({name:"export_type",value:exportType})
    
    if (exportType == "agg") {
        query_args.push({name:"filename",value:$("#export-file-name-agg").val() + ".csv"});
    } else {
        query_args.push({name:"filename",value:$("#export-file-name-example").val() + ".csv"});
        var extent_dec = $("input[name=export-extent]:checked").val();
        var pagingInfo = examplesTable.page.info();
        
        switch(extent_dec) {
            case "page":
                query_args.push({name:"examples_start",value:pagingInfo.start});
                query_args.push({name:"num_examples",value:pagingInfo.length});
                break;
            case "pages":
                var startPage = Number($("#export-start-page").val()) - 1;
                var endPage = Number($("#export-end-page").val()) - 1;
                query_args.push({name:"examples_start",value:startPage * pagingInfo.length});
                query_args.push({name:"num_examples",value:(endPage - startPage + 1) * pagingInfo.length});
                
                break;
            case "all":
                query_args.push({name:"num_examples",value:"*"})
                break;
            case "rows":
                query_args.push({name:"examples_start",value:0});
                query_args.push({name:"num_examples",value:Number($("#export-rows").val())});
                break;
        }
        
        
        var features_dec = $("input[name=export-features]:checked").val();
        var features = []
        
        if (features_dec == "all") {
            $(".toggle-visibility").each(function() {
                features.push($(this).text());
            });
        } else {
            $(".toggle-visibility").each(function() {
                var current_feature = $(this);
                if (!current_feature.hasClass("feature-invisible")) {
                    features.push(current_feature.text());
                }
            });
        }
        
        query_args.push({name:"features",value:features});
    }
    

    var query = PREFIX+'/export?args='+JSON.stringify(query_args);

    window.open(query);
}

