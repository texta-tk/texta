var PREFIX = LINK_GRAMMAR_BUILDER;

var COMPONENTS = {};
var componentNames = [];

var CONSTRUCTS = [];

function addComponent() {
    var name = $("#new-component-name").val();
    var type = $("#new-component-type").val();
    var content = $("#new-component-content").val();
    
    if (name && type && content) {
        $("#new-component-name").val("");
        $("#new-component-type").val("");
        $("#new-component-content").val("");
        
        var newComponentInfo = $("#component-info-template").clone().toggleClass("hidden").removeAttr("id");
        
        newComponentInfo.find("div[name='component-name']").html(name);
        newComponentInfo.find("span[name='component-type']").html(type);
        newComponentInfo.find("pre[name='component-content']").html(content);
        
        $("#components").append(newComponentInfo);
        
        COMPONENTS[name] = {name:name,type:type,content:content};
        componentNames.push(name);
        
        $("#component-to-add").append($("<option/>").attr("value",name).text(name));
    }
    
}

function addComponentToConstruct() {
    var component = $("#component-to-add").val()
    
    var newAddedComponent = $("#added-component-template").clone().toggleClass("hidden").removeAttr("id").text(component);
    
    newAddedComponent.on('click',function() {$(this).remove();});
    
    $("#added-components").append(newAddedComponent);
}

function addConstruct() {
    var name = $("#new-construct-name").val();
    var components = [];
    
    $("#added-components > button").each(function() {
        components.push($(this).text());
    });
    
    var separator = $("new-construct-separator").val() ? $("new-construct-separator").val() : "\s+";
    
    if (name && components) {
        var newConstruct = $("#added-construct-template").clone().toggleClass("hidden").removeAttr("id");
        
        newConstruct.find("div[name='construct-name']").html(name);
        var componentsDiv = newConstruct.find("div[name='construct-components']");
        
        for (var i = 0; i < components.length; i++) {
            var constructComponentBtn = $("#added-component-template").clone().toggleClass("hidden").removeAttr("id").text(components[i]);
            componentsDiv.append(constructComponentBtn);
        }
        
        newConstruct.find("p[name='construct-separator']").html("Separator: " + separator);
        
        $("#constructs").append(newConstruct);
        
        var componentObjs = [];
        for (var i = 0; i < components.length; i++) {
            //console.log(components[i]);
            //console.log(COMPONENTS);
            componentObjs.push(COMPONENTS[components[i]]);
        }
        
        console.log(componentObjs);
        
        CONSTRUCTS.push({name:name, components:componentObjs, separator:separator})
    }
    
}

function display(){
    
    var request = new XMLHttpRequest();

    var formData = new FormData();
    
    var searchId = $("#search-selector").val();
    formData.append("searchId",searchId);

    var feature = $("#feature-selector").val();
    formData.append("feature",feature);
    
    request.onreadystatechange=function() {
        if (request.readyState==4 && request.status==200) {
            $("#result").html(request.responseText);
            examplesTable = $('#datatable').DataTable({"bAutoWidth": false,
                                                      "bServerSide":true,
                                                      "sAjaxSource": PREFIX+"/get_table_data",
                                                      "sDom": '<"H"ipr>t<"F"lp>',
                                                      "sServerMethod":"GET",
                                                      "fnServerParams":function(aoData){
                                                          aoData.push({'name':'feature','value':feature});
                                                          aoData.push({'name':'search_id','value':searchId});
                                                          aoData.push({'name':'constructs','value':JSON.stringify(CONSTRUCTS)});
                                                       },
                                                      "columnDefs": [
                                                        {
                                                          "targets": [1],
                                                          "visible": false,
                                                        },
                                                      ],
                                                      "fnRowCallback": function(nRow, aData) {
                                                          var match = aData[1];
                                                          var $nRow = $(nRow);
                                                          $nRow.removeClass('even').removeClass('odd');
                                                          if (match) {
                                                              $nRow.css({"background-color":"#80FF88"});
                                                          } else {
                                                              $nRow.css({"background-color":"#FF5757"});
                                                          }
                                                      }
            });
            /*
            var dataset = $("#dataset").val();
            var mapping = $("#mapping").val();
            loadUserPreference(dataset,mapping);
            $("#actions-btn").removeClass("invisible");
            $("#export-examples-modal").removeClass("invisible");
            $("#export-aggregation-modal").addClass("invisible");
            */
        }
    }

    request.open("POST",PREFIX+'/get_table');
    request.send(formData);
}