/*
 * 
 * Selection frame inspired by Lars Gersmann's code at http://bl.ocks.org/lgersman/5311083
 * 
 */

COLOUR_TERM = 'black';
COLOUR_TERM_SELECTED = 'green';
COLOUR_TERM_SELECTED_TMP = 'red';
COLOUR_CONCEPT = 'blue';
COLOUR_CONCEPT_SELECTED = 'yellow';

var PREFIX = LINK_CONCEPTUALISER;

var CURRENT_LEXICONS;

var global_data;

var CTRL_DOWN = false;

var padding = 60;
var r = 5;
var r_merged = 8;

var x,y;

$(document).ready(function(){
    $("#onto_svg_and_menu").css("height",$(document).height()-80-document.getElementById("onto_svg_and_menu").getBoundingClientRect().top);
    $("#plot_settings").toggle(0);
    $("#legend").toggle(0);

    $("#plot_btn").on('click',(function() {
        $("#plot_settings").toggle(0);
    }));

    $("#legend_btn").on('click',(function() {
        $("#legend").toggle(0);
    }));

    $("#save_btn").on('click',(function() {
        save();
    }));
    
});

document.onkeydown = function(event) {
    var key = event.which ? event.which : event.keyCode;
    if (key == 17) {
        CTRL_DOWN = true;
    }
}

document.onkeyup = function(event) {
    var key = event.which ? event.which : event.keyCode;
    if (key == 17) {
        CTRL_DOWN = false;
    }
}

function save() {
    var svg = d3.select("#svg");
    var concepts = svg.selectAll(".merged_circle");
    var concept_data = [];
    for (var i = 0; i < concepts[0].length; i++) {
        var concept = $(d3.select(concepts[0][i])[0]);
        var label = concept.data("label");
        var id = concept.data("id");
        var term_data = d3.selectAll(concept.data("terms")).data();
        var ids = []
        for (var j = 0; j < term_data.length; j++) {
            ids.push(term_data[j].id);
        }
        var concept_datum = {descriptive_term_id:id, term_ids:ids};
        concept_data.push(concept_datum);
    }

    var terms = svg.selectAll(".circle");
    var term_data = [];
    for (var i = 0; i < terms[0].length; i++) {
        if (d3.select(terms[0][i]).attr("visibility") == "hidden") {
            continue;
        } else {
            term_data.push(d3.select(terms[0][i]).data()[0].id);
        }
    }

    var xmlhttp = new XMLHttpRequest();
    xmlhttp.onreadystatechange=function() {
        if (xmlhttp.readyState==4 && xmlhttp.status==200) {
            swal('Success!','Concepts saved!','success');
        }
    }

    var form_data = new FormData();
    form_data.append("concepts",JSON.stringify(concept_data));
    form_data.append("terms",JSON.stringify(term_data));
    xmlhttp.open("POST",PREFIX + "/save",true);
    xmlhttp.send(form_data);    
}

function expand_selected() {
    var svg = d3.select("#svg");
    var selected = svg.selectAll(".selected").filter(".merged_circle");
    if (!selected.empty()) {
        
        var terms = [];

        selected.each(function() {
            var selected_terms = $(this).data("terms")
            for (var i = 0; i < selected_terms.length ; i++) {
                terms.push(selected_terms[i]);
            }
        });
        
        d3.selectAll(terms).attr("visibility","visible").each(function(circle_data,i) {
            $(d3.select(this)[0]).data("label").attr("visibility","visible");
        });
        
        selected.each(function() {
            $(this).data("label").remove()
        });
        
        selected.remove();
        $("#concept_content").hide(0);
        return d3.selectAll(terms);
    }
    return [];
}

function merge(class_label) {
    var svg = d3.select("#svg");
    var new_circle;
    if(!svg.selectAll("." + class_label).empty()) {
        var total_x = 0;
        var total_y = 0;
        var N = 0;
        var terms = [];
        svg.selectAll("." + class_label).each(function(circle_data,i) {
            if (d3.select(this).attr("visibility") != "hidden") {
                total_x += circle_data.x;
                total_y += circle_data.y;
                N += 1;
                terms.push(this);
            }
        });

        var avg_x = total_x/N;
        var avg_y = total_y/N;
        svg.selectAll("." + class_label).attr("visibility","hidden").each(function(circle_data,i) {
            $(d3.select(this)[0]).data("label").attr("visibility","hidden");
        });

        d3.selectAll("circle."+class_label).classed(class_label,false);

        new_circle = svg.append("circle")
            .attr("class","merged_circle selected")
            .attr("cx", x(avg_x))
            .attr("cy", y(avg_y))
            .attr("r",r_merged)
            .on("mousedown",function() {
            if (!d3.selectAll('circle.selected').empty() && d3.selectAll('circle.selected').classed("merged_circle") && d3.select(this).classed("merged_circle")) {
                // Select concept
                
                if (CTRL_DOWN) {
                    d3.select(this).classed("selected",true);
                } else {
                    d3.selectAll('circle.selected').classed("selected",false);
                    d3.select(this).classed("selected",true);
                    populate_concept_contents();
                    populate_concept_label_selection();
                }

                d3.event.stopPropagation();
                
            } else if(!d3.selectAll('circel.selected').empty() && d3.selectAll('circle.selected').classed("circle") && CTRL_DOWN) {
                d3.select(this).classed("selected",true);
                d3.event.stopPropagation();
            } else if(!d3.selectAll('circle.selected').empty() && !d3.select(this).classed("selected")) {
                // Add terms to concept
                var svg = d3.select("#svg");
                
                var tmp = svg.selectAll('circle.selected').classed("selection2",true).classed("selected",false);
                
                var selected = d3.select(this).classed("selected",true);
                terms = $(selected[0]).data("terms");
                expand_selected();
                
                d3.selectAll(terms).classed("selection2",true);
                
                var merged_circle = merge("selection2");
                merged_circle.classed("selected",true);
                
                display_concept_window();
                set_most_freq_term_as_label(merged_circle);
                
                d3.event.stopPropagation();
                
            } else if(d3.select(this).classed("selected")) {
                d3.select(this).classed("selected",false);
            } else {
                d3.select(this).classed("selected",true);
                display_concept_window();
                
                d3.event.stopPropagation();
            }
        });
            
        $(new_circle[0]).data("terms",terms);
    }
    return new_circle;
}

function draw_plot(data) {
    global_data = data;
    
    var svg_div_dim = document.getElementById("onto_svg_and_menu").getBoundingClientRect();
    
    var width = svg_div_dim.width;
    var height = svg_div_dim.height;

    var svg = d3.select("#svg").style("width",width).style("height",height-10).attr("width", "100%").attr("height", "100%");
    
    svg.selectAll("*").remove();

    var all_terms = $.merge([],data.terms);
    
    for (var i = 0; i < data.concepts.length; i++) {
        all_terms = $.merge(all_terms,data.concepts[i].terms);
    }
    
    x = d3.scale.linear().domain(d3.extent(all_terms, function(d) {return d.x;})).range([padding,width-padding]);
    y = d3.scale.linear().domain(d3.extent(all_terms, function(d) {return d.y;})).range([padding,height-padding]);

    var tooltip = d3.select("#tooltip").style("opacity",0);
    
    add_term_points(svg,data.terms,x,y)
    
    var terms = $.merge([],data.terms)
    
    for (var i = 0; i < data.concepts.length; i++) {
        var concept = data.concepts[i];
        var term_points = add_term_points(svg,$.merge(terms,concept.terms),x,y);
        term_points.classed("selected",true);
        var concept_circle = merge("selected").classed("selected",false);
        add_concept_label(concept_circle,concept.descriptive_term,concept.descriptive_term_id);
    }
    
    svg
	.on( "mousedown", function() {
	    $("#concept_content").hide(0);
	    if (d3.event.defaultPrevented) return;
        
        if (!CTRL_DOWN) {
            d3.selectAll('circle.selected').classed( "selected", false);
        }
        
	    var p = d3.mouse( this);

	    svg.append( "rect")
	    .attr({
		rx      : 6,
		ry      : 6,
		class   : "selection",
		x       : p[0],
		y       : p[1],
		width   : 0,
		height  : 0
	    })
	})
	.on( "mousemove", function() {
	var s = svg.select( "rect.selection");

	if( !s.empty()) {
	    var p = d3.mouse( this),
		d = {
		    x       : parseInt( s.attr( "x"), 10),
		    y       : parseInt( s.attr( "y"), 10),
		    width   : parseInt( s.attr( "width"), 10),
		    height  : parseInt( s.attr( "height"), 10)
		},
		move = {
		    x : p[0] - d.x,
		    y : p[1] - d.y
		}
	    ;

	    if(move.x > 0) {
		d.width = move.x;
	    }
	    if(move.y > 0) {
		d.height = move.y;
	    }
	    s.attr( d);

	    d3.selectAll( '.selected').classed( "selected", false);

	    d3.selectAll( '.circle').each( function( circle_data, i) {
		    circle_x = x(circle_data.x);
		    circle_y = y(circle_data.y);
            var current_circle = d3.select(this);
            if(
                current_circle.attr("visibility") != "hidden" &&
                !current_circle.classed( "selected") &&
                circle_x>=d.x && circle_x<=d.x+d.width &&
                circle_y>=d.y && circle_y<=d.y+d.height
            ) {
                current_circle
                .classed( "selection", true)
                .classed( "selected", true);
            }
	    });

        d3.selectAll('.merged_circle').each(function() {
            circle_x = $(this).attr("cx");
            circle_y = $(this).attr("cy");
            if(
                !d3.select( this).classed( "selected") &&
                circle_x>=d.x && circle_x<=d.x+d.width &&
                circle_y>=d.y && circle_y<=d.y+d.height
            ) {

                d3.select( this)
                .classed( "selection", true)
                .classed( "selected", true);
            }
        });
	}
    })
    .on( "mouseup", function() {
	// remove selection frame
	svg.selectAll( "rect.selection").remove();

	    // remove temporary selection marker class
	d3.selectAll( '.selection')
	    //.attr("fill","black")
	    .classed( "selection", false);
    })
    .on( "mouseout", function() {
	if( d3.event.relatedTarget && d3.event.relatedTarget.tagName=='HTML') {
		// remove selection frame
	    svg.selectAll( "rect.selection").remove();

		// remove temporary selection marker class
	    d3.selectAll( '.selection')
		.attr("fill","black")
		//.classed( "selection", false);
	    d3.selectAll('.selected').attr("fill","green");
	}
    });
}

function add_term_points(svg_obj,data,x_scale,y_scale) {
    var term_points = svg_obj.selectAll(".circle")
                        .data(data)
                        .enter()
                        .append("circle")
                        .attr("class","circle")
                        .attr("cx", function(d) { return x_scale(d.x); })
                        .attr("cy", function(d) { return y_scale(d.y); })
                        .attr("r",r)
                        .text(function(d) { return d.term; })//;
                        .on("click", function(d) {
                            d3.select("#svg").selectAll("circle.merged_circle.selected").classed("selected",false);
                            
                            if (!CTRL_DOWN) {
                                d3.select(this).classed("selected",true);
                            } else {
                                if (d3.select(this).classed("selected")) {
                                    d3.select(this).classed("selected",false);
                                } else {
                                    d3.select(this).classed("selected",true);
                                }
                            }
                            
                            d3.event.stopPropagation();
                        })

                        .each(function(circle_data,i) {
                            var parent_circle = d3.select(this);
                            svg_obj.append("text")
                            .attr("x", function(d) { return x_scale(circle_data.x)+5; })
                            .attr("y", function(d) { return y_scale(circle_data.y)-18; })
                            .text(circle_data.term)
                            .attr("class","unselectable")
                            .each(function(text_data,i) {
                                $(parent_circle[0]).data("label",d3.select(this));
                            });
                        });
                       
    return term_points;
}

function add_label(d3_object,x,y,label) {
    d3.select("#svg").append("text")
		.attr("x",x)
		.attr("y",y)
		.text(label)
		.attr("class","unselectable")
		.each(function(text_data,i) {
		    $(d3_object[0]).data("label",d3_object);
		});
}

function populate_concept_label_selection() {
    var selected_concept = $(d3.select(".selected")[0]);
    
    var term_data = d3.selectAll(selected_concept.data("terms")).data();
    term_data.sort(function(term1,term2) {return term2.count-term1.count;});
    
    var select = document.getElementById("label_selection_field");
    select.options.length = 0; //empty options
    
    for (var i = 0; i < term_data.length; i++) {
	select.options[select.options.length] = new Option(term_data[i].term, term_data[i].id, false, false);
    }
}

function handle_concept_label_selection() {
    
    var selected_option_field = document.getElementById("label_selection_field");
    
    var selected_label = selected_option_field.options[selected_option_field.selectedIndex].text;
    var selected_label_id = parseInt(selected_option_field.options[selected_option_field.selectedIndex].value);
    
    add_concept_label(d3.select(".selected"),selected_label,selected_label_id);
}

function add_concept_label(concept_obj,label,label_id) {
    var concept_obj_jq = $(concept_obj[0]).data("id",label_id);

    var label = d3.select("#svg")
                    .append("text")
                    .attr("x",parseInt(concept_obj.attr("cx"))+5)
                    .attr("y",parseInt(concept_obj.attr("cy"))-18)
                    .text(label)
                    .attr("class","unselectable")
                    .each(function(text_data,i) {
                        if (concept_obj_jq.data("label")) {
                            concept_obj_jq.data("label").remove();
                        }
                        concept_obj_jq.data("label",d3.select(this));
                    });
                    
    return label;
}

function populate_concept_contents() {
    var selected_circle = $(d3.select(".selected")[0]);
   
    var table = document.getElementById("content_table");
    // empty table
    while (table.firstChild) {
	table.removeChild(table.firstChild);
    }
    
    var terms = d3.selectAll(selected_circle.data("terms")).data();
    terms.sort(function(term1,term2) {return term2.count-term1.count;});
    
    for (i = 0; i < terms.length; i++) {
        var tr = document.createElement('TR');
        var td = document.createElement('TD');
        td.appendChild(document.createTextNode(terms[i].term));
        tr.appendChild(td);
        tr.className = "content_item";
        table.appendChild(tr);
    }
    
} 

function display_concept_window() {
    populate_concept_label_selection();
    populate_concept_contents();
    $("#concept_content").show(0);
}

function set_most_freq_term_as_label(concept_circle) {
    var selected_circle = $(concept_circle[0]);
    
    var terms = d3.selectAll(selected_circle.data("terms")).data();
    terms.sort(function(term1,term2) {return term2.count-term1.count;});
    
    var most_freq_term = terms[0];
    
    add_concept_label(selected_circle,most_freq_term.term,most_freq_term.id);
    
}

$(document).on("keydown", function(e) {
    switch(e.which) {
        case 13:
            if (d3.select(".selected").empty()) return;

            var selected_terms = d3.selectAll(".selected").filter(".circle").classed("selected",false);

            if (!d3.selectAll(".selected").empty() && d3.selectAll(".selected").classed("merged_circle")) {
                var terms = expand_selected();
                terms.classed("selected",true);
            }

            selected_terms.classed("selected",true);

            var merged_circle = merge("selected");
            display_concept_window();
            set_most_freq_term_as_label(merged_circle);
            
            break;
        case 46:
            expand_selected();
            d3.selectAll(".selected").classed("selected",false);
            break;
    }
});

$('body').on('click','.content_item',function(e){
    var removed_term = $(this).closest('tr').children().first().text()

    var terms = $(d3.select(".selected")[0]).data('terms')
    
    var prev_concept_label = $(d3.select(".selected")[0]).data('label').text();
    var prev_concept_id = $(d3.select(".selected")[0]).data('id');
    
    var i = 0;
    
    for (; i < terms.length; i++) {
        if (d3.select(terms[i]).data()[0].term == removed_term) {
            break;
        }
    }
    
    var removed_term_d3 = d3.select(terms[i]);
    terms.splice(i,1)
    
    removed_term_d3.attr("visibility","visible");
    $(removed_term_d3[0]).data("label").attr("visibility","visible");
    
    var expanded_terms = expand_selected();
    expanded_terms.classed("selected",true);
    
    if (terms.length) {
        var merged_circle = merge("selected");
        merged_circle.classed("selected",true);
        if (removed_term == prev_concept_label) {
            set_most_freq_term_as_label(merged_circle);
        } else {
            add_concept_label(merged_circle,prev_concept_label,prev_concept_id);
        }
        $("#concept_content").show(0);
    } else {
        $("#concept_content").hide(0);
    }
    
    $(this).closest('tr').remove();
})

function populate_form_lexicons(form_id,lexicons) {
    var form = document.getElementById(form_id);
    
    while (form.firstChild) {
	form.removeChild(form.firstChild);
    }
    
    var fieldset = document.createElement('fieldset');
    var legend = document.createElement('legend');
    legend.appendChild(document.createTextNode('Lexicons'));
    fieldset.appendChild(legend);
    
    for (var i = 0; i < lexicons.length; i++) {
	var checkbox = document.createElement('input');
	checkbox.type="checkbox";
	checkbox.value=lexicons[i].id.toString();
	checkbox.title=lexicons[i].desc;
	checkbox.name="plot_cb";
	checkbox.id="cb"+lexicons[i].id.toString();
	
	var label = document.createElement('label');
	label.htmlFor = "cb"+lexicons[i].id.toString();
	label.appendChild(document.createTextNode(lexicons[i].name));
	label.title=lexicons[i].desc;
	
	fieldset.appendChild(checkbox);
	fieldset.appendChild(label);
	fieldset.appendChild(document.createElement('br'));
    }
    form.appendChild(fieldset);
    
    var methods = ["PCA","TSNE","MDS"];
    
    var label = document.createTextNode("Method: ")
    
    var select = document.createElement('select');
    select.id="method_name";
    
    for (var i = 0; i < methods.length; i++) {
        var option = document.createElement('option');
        option.value = methods[i];
        option.text = methods[i];
        select.appendChild(option);
    }
    
    form.appendChild(label);
    form.appendChild(select);
    
    var submit = document.createElement('input');
    submit.type="submit";
    submit.value="Plot data";
    
    form.appendChild(document.createElement('br'));
    form.appendChild(submit);
}

function get_lexicons_for_plotting() {
    
    var xmlhttp = new XMLHttpRequest();
    xmlhttp.onreadystatechange=function() {
	if (xmlhttp.readyState==4 && xmlhttp.status==200) {
	    populate_form_lexicons("plot_settings_form",JSON.parse(xmlhttp.responseText));
	}
    }

    xmlhttp.open("POST",PREFIX + "/get_lexicons",true);
    xmlhttp.send();
}

function ends_with(str, suffix) {
    return str.indexOf(suffix, str.length - suffix.length) !== -1;
}

function plot_lexicons() {
    
    $("#plot_settings").hide(0);
    
    var chosen_lexicons = new Array();
    
    $("input:checkbox[name=plot_cb]:checked").each(function() {
        chosen_lexicons.push(parseInt($(this).val()));
    });
    
    var xmlhttp = new XMLHttpRequest();
    xmlhttp.onreadystatechange=function() {
        if (xmlhttp.readyState==4 && xmlhttp.status==200 && xmlhttp.responseURL && !ends_with(xmlhttp.responseURL,"load")) {
                go_to(xmlhttp.responseURL);
        } else {
            $('#svg').height(function(index, height) {
                return window.innerHeight - $(this).offset().top - $("#top_line").height()-40;
            });

            if (xmlhttp.responseText) {
                draw_plot(JSON.parse(xmlhttp.responseText));
            }else{

            }
            CURRENT_LEXICONS = chosen_lexicons;
        }
    }

    var form_data = new FormData();
    form_data.append("lids",JSON.stringify(chosen_lexicons))
    
    var select = document.getElementById("method_name")
    form_data.append("method",select.options[select.selectedIndex].value);
        
    xmlhttp.open("POST",PREFIX + "/load",true);
    xmlhttp.send(form_data);
    
}
