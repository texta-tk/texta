var PREFIX = LINK_GRAMMAR_BUILDER;

var COMPONENTS = {};
var componentNames = [];

var CONSTRUCTS = [];

$('#save-component-btn').click(function() {
   saveComponent(); 
});

$('#add-sub-component-btn').click(function() {
    addSubComponent();
});

$('#existing-component-selection').on("change",function() {
    console.log($(this).val());
    $.get(PREFIX+"/get_component_json", {id:$(this).val()}, function(data) {
        $('#component-json-box').html(JSON.stringify(JSON.parse(data),undefined,4));
    })
});

$('a[href=#test-grammar-tab]').click(function() {
    //loadComponentsInto('inclusive-grammar-selection');
    //loadComponentsInto('exclusive-grammar-selection');
});

$('#match-grammar-btn').click(function() {
    display_table('positive');
    display_table('negative');
})

function saveComponent() {
    var name = $("#new-component-name").val();
    var type = $("#new-component-type").val();
    var metatype = $("#new-component-metatype").val();
    
    //$("#new-component-name").val('');
    
    var data = {name:name, type:type}
    
    if (metatype == 'basic') {
        if (type == 'exact') {
            data['content'] = JSON.stringify($("#basic-content").val().split('\n'));
            data['join_by'] = $('#exact-join-by').val();
        } else {
            data['content'] = $("#basic-content").val()
        }
        data['sub_components'] = '[]';
        //$("#basic-content").val('');
        
        data['layer'] = $('#new-component-layer').val()
        //$('#new-component-layer').val('')
    } else {
        var components = [];
        $("#sub-components > button").each(function() {
            components.push($(this).attr('data-id'));
        });

        data['content'] = '';
        data['sub_components'] = JSON.stringify(components);
        $("#sub-components").html('');
    }
    
    $.post(PREFIX+'/save_component', data, function(data) {
        var opt = document.createElement('option');
        opt.value = data.id;
        opt.innerHTML = name;
        document.getElementById('existing-component-selection').appendChild(opt);
    },'json')    
}

function loadComponentsInto(selection_id) {
    $('#'+selection_id).html('')
    $.get(PREFIX+'/get_components', function(data) {
        var sel = document.getElementById(selection_id);
        for (var i = 0; i < data.length; i++) {
            var opt = document.createElement('option');
            opt.value = data[i].id;
            opt.innerHTML = data[i].id + ' - ' + data[i].name;
            sel.appendChild(opt);
        }
    },'json')    
}

function addSubComponent() {
    var selection = document.getElementById('existing-component-selection')
    var value = selection.options[selection.selectedIndex].value;
    var name = selection.options[selection.selectedIndex].text;
    
    var button = $('<button>',{
        "class":"btn btn-info",
        "data-id":value,
        "click":function() {
            $(this).remove();
        }
    });
    button.text(name);
    $("#sub-components").append(button);
}

function display_table(polarity, is_test = false) {
    var searchId = $("#search-selection").val();
    var inclusiveGrammarId = $("#inclusive-grammar-selection").val();
    var exclusiveGrammarId = $("#exclusive-grammar-selection").val();
    
    $.get(PREFIX+'/get_table', {polarity:polarity,
                                search_id:searchId,
                                inclusive_grammar_id:inclusiveGrammarId,
                                exclusive_grammar_id:exclusiveGrammarId,
                                inclusive_test_grammar:inclusiveTestGrammarJson,
                                is_test:is_test
                                }, 
          function(data) {
        $("#" + (polarity == 'positive' ? 'matched' : 'unmatched') + "-documents-content").html(data);
            examplesTable = $('#'+polarity+'_datatable').DataTable({"bAutoWidth": false,
                                                      "bServerSide":true,
                                                      "sAjaxSource": PREFIX+"/get_table_data",
                                                      "sDom": '<"H"ipr>t<"F"lp>',
                                                      "sServerMethod":"GET",
                                                      "fnServerParams":function(aoData){
                                                          aoData.push({'name':'polarity','value':polarity});
                                                          aoData.push({'name':'search_id','value':searchId});
                                                          aoData.push({'name':'inclusive_grammar_id','value':inclusiveGrammarId});
                                                          aoData.push({'name':'exclusive_grammar_id','value':exclusiveGrammarId});
                                                          aoData.push({'name':'inclusive_test_grammar','value':inclusiveTestGrammarJson});
                                                          aoData.push({'name':'is_test','value':is_test})
                                                       },
                                                      "fnRowCallback": function(nRow, aData) {
                                                            var $nRow = $(nRow);
                                                            if (polarity == 'positive') {
                                                                $nRow.css({"background-color":"#dffec2"});
                                                            } else {
                                                                $nRow.css({"background-color":"#fedcdc"});
                                                            }
                                                      }
            });
    })
}

var treeData;

var nodeId = 0;
var currentNode;
var inclusiveTestGrammarJson;

function grammarContextMenu(node) {
// From http://stackoverflow.com/questions/4559543/configuring-jstree-right-click-contextmenu-for-different-node-types
    var $tree = $('#new-grammar-tree').jstree(true);
    var items = {
        addBasicItem: {
            label: 'Add basic',
            action: function(obj) {  
                $tree.create_node(node,{id:'node_'+nodeId, text:'New terminal',state:'open',type:'new_basic',data:{operation:'',content:'',layer:'',metatype:'basic'}}, 'last', false, false);
                nodeId++;
                $tree.open_all()
            }
        },
        addAggregationItem: {
            label: 'Add aggregation',
            separator_after: true,
            action: function(obj) {
                $tree.create_node(node, {id:'node_'+nodeId, text:'New aggregation',state:'open',type:'new_aggregation',data:{operation:'',metatype:'aggregation'}}, 'last', false, false);
                nodeId++;
                $tree.open_all()
            }
        },
        renameItem: {
            label: "Rename",
            action: function (obj) { $tree.edit(node) }
        },
        testItem: {
            label: "Test",
            action: function (obj) { 
                test(node);
            }
        },
        deleteItem: {
            label: "Delete",
            action: function (obj) { $tree.delete_node(node) }
        }
        
    };

    if (node.data.metatype == "basic") {
        delete items.addBasicItem;
        delete items.addAggregationItem;
    }
    
    return items;
}

function test(node) {
    var $tree = $('#new-grammar-tree').jstree(true);
    $('.nav-pills a[href="#test-grammar-tab"]').tab('show');
    inclusiveTestGrammarJson = JSON.stringify(jstreeToNestedGrammar($tree.get_json(node)));
    display_table('positive',true);
    display_table('negative',true);
}


function saveGrammarTree() {
    grammar_json = JSON.stringify($('#new-grammar-tree').jstree(true).get_json())
    $.post(PREFIX+'/save_grammar',{json:grammar_json}, function(data) {
        var grammar_id = JSON.parse(data).id
        var root_node = $('#new-grammar-tree').jstree(true).get_node('new')
        if (root_node) {
            root_node.id = grammar_id
        }
        loadGrammars();
    })
}
 
function loadGrammarTree(id) {
    
    $.getJSON(PREFIX+'/get_grammar', {id:id}, function(data) {
        initializeTree(data)
    });
}

function deleteGrammarTree(id) {
    if (id == 'new') {
        return
    }
    
    $.get(PREFIX+'/delete_grammar',{id:id}, function() {
        loadGrammars();
        initializeTree();
    });
}

function loadGrammars() {
    $.getJSON(PREFIX+'/get_grammar_listing', '', function(data) {
        selection = $('#selected-grammar');
        selection.html('')
        
        selection.append($('<option></option>').val('new').html('New grammar...'))
        
        for (var i=0; i < data.length; i++) {
            var datum = data[i];
            selection.append($('<option></option>').val(datum.id).html(datum.name + ' [' + datum.last_modified + ']'));
        }
    })
}

function setAggregationTypes(parent_operation) {
    var types;
    
    if (parent_operation == 'gap' || parent_operation == 'concat') {
        types = [{name:'Union', value:'union'}];
    } else {
        types = [{name:'Intersection',value:'intersect'}, 
                    {name:'Union',value:'union'},
                    {name:'Concatenation',value:'concat'},
                    {name:'Gap',value:'gap'}];
    }
    
    var selection = $('#aggregation-type');
    selection.html('')
    
    for (var i = 0; i < types.length; i++) {
        type = types[i];
        selection.append($('<option></option>').val(type.value).html(type.name));
    }
}

var aggregationChildren = ["new_basic","new_aggregation","exact","regex","intersect","concat","gap","union"]

function initializeTree(data) {
    var $tree = $('#new-grammar-tree');
    
    if ($tree.hasClass('jstree')) {
        $tree.jstree(true).destroy();
    }
    
    if (data == undefined) {
        data = [{'id':'new', 'text':'My grammar','children':[],'type':'root','data':{'metatype':'root', 'operation':''}}]
    }
    
    console.log(data);
    
    $tree.jstree({
       'core': {
           'animation': 0,
           'check_callback': true,
           'data': data
        },
        'types': {
            "#" : {
                "valid_children" : ["root"]
            },
            "root" : {
                "icon" : STATIC_URL+"grammar_builder/icons/na.ico",
                 "valid_children" : aggregationChildren
            },
            "new_basic" : {
                "icon" : STATIC_URL+"grammar_builder/icons/na.ico",
                 "valid_children" : ["none"]
            },
            "exact" : {
                "icon" : STATIC_URL+"grammar_builder/icons/exact.ico",
                 "valid_children" : ["none"]
            },
            "regex" : {
                "icon" : STATIC_URL+"grammar_builder/icons/regex.ico",
                 "valid_children" : ["none"]
            },
            "new_aggregation" : {
                "icon" : STATIC_URL+"grammar_builder/icons/na.ico",
                "valid_children" : aggregationChildren
            },
            "intersect" : {
                "icon" : STATIC_URL+"grammar_builder/icons/and.ico",
                 "valid_children" : aggregationChildren
            },
            "union" : {
                "icon" : STATIC_URL+"grammar_builder/icons/or.ico",
                 "valid_children" : aggregationChildren
            },
            "concat" : {
                "icon" : STATIC_URL+"grammar_builder/icons/concat.ico",
                 "valid_children" : aggregationChildren
            },
            "gap" : {
                "icon" : STATIC_URL+"grammar_builder/icons/gap.ico",
                 "valid_children" : aggregationChildren
            },
        },
        'plugins': ['contextmenu','dnd','types'],
        'contextmenu': {'items': grammarContextMenu}
    }).
    on("select_node.jstree", function(event, data) {
        currentNode = data.node;
        
        $('#limited-aggregation-type-div').addClass('hidden');
        $('#aggregation-type-div').removeClass('hidden');
        
        var parentNode = $('#new-grammar-tree').jstree(true).get_node(currentNode.parent)
        var parentOperation;
        
        if (parentNode.id != '#') {
            parentOperation = parentNode.data.operation;
        } else {
            parentOperation = 'NA';
        }
        
        setAggregationTypes(parentOperation);
        
        if (data.node.data.metatype == 'basic') {
            $('#basic-details').removeClass('hidden');
            $('#aggregation-details').addClass('hidden');
            
            if (currentNode.data.operation == '') {
                $('#basic-type').val('exact');
            } else {
                $('#basic-type').val(currentNode.data.operation);
            }
            $('#basic-layer').val(currentNode.data.layer);
            if (currentNode.data.content.length > 0) {
                $('#basic-content').val(currentNode.data.content.join('\n'))
            }
        } else {
            if (data.node.data.metatype == 'aggregation' || data.node.data.metatype == 'root') {
                $('#basic-details').addClass('hidden');
                $('#aggregation-details').removeClass('hidden');
                
                if (currentNode.data.operation == '') {
                    $('#aggregation-type').val('union');
                } else {
                    $('#aggregation-type').val(currentNode.data.operation);
                }
            }
        }
    });
}

function jstreeToNestedGrammar(jstree) {
    
    console.log(jstree)
    
    function traverse(tree) {
        console.log(tree)
        var components = []
        for (var i = 0; i < tree.children.length; i++) {
            components.push(traverse(tree.children[i]));
        }
        var new_component = {}
        
        if (components.length > 0) {
            new_component.components = components;
        }
        
        new_component.name = tree.text;
        new_component.operation = tree.data.operation;
        
        new_component.id = tree.id;
        if ('layer' in tree.data) {
            new_component.layer = tree.data.layer;
        }
        
        if ('sensitive' in tree.data) {
            new_component.sensitive = tree.data.sensitive;
        }
        
        if ('matchFirst' in tree.data) {
            new_component.matchFirst = tree.data.matchFirst;
        }
        
        if ('content' in tree.data) {
            if (tree.data.operation == 'exact') {
                new_component.terms = tree.data.content;
            } else {
                if (tree.data.operation == 'regex') {
                    new_component.expression = tree.data.content[0]
                }
            }
        }
        if (new_component.operation == 'gap') {
            new_component.slop = tree.data.slop;
        }

        return new_component;
    }
    
    return traverse(jstree);
}

initializeTree();

$('#save-details-btn').click(function() {
    var type = currentNode.data.metatype;
    
    if (type == 'basic') {
        currentNode.data.operation = $('#basic-type').val();
        currentNode.data.layer = $('#basic-layer').val();
        currentNode.data.content = $('#basic-content').val().split(/\r*\n/);
        currentNode.data.sensitive = $('#basic-sensitivity').prop('checked');
    } else {
        if (type == 'aggregation' || type == 'root') {
            currentNode.data.operation = $('#aggregation-type').val();
            if (currentNode.data.operation == 'gap') {
                currentNode.data.slop = $('#gap-slop').val();
                currentNode.data.matchFirst = $('#gap-match-first').prop('checked');
            }
        }
    }
    
    $('#new-grammar-tree').jstree(true).set_type(currentNode,currentNode.data.operation); // change icon
});

$('#test-whole-tree-btn').click(function() {
    test($('#new-grammar-tree').jstree(true).get_json()[0]);
})

$('#aggregation-type').change(function() {
    if ($(this).val() == 'gap') {
        $('#gap-params').removeClass('hidden');
    } else {
        $('#gap-params').addClass('hidden');
    }
})

$('#load-grammar-btn').click(function() {
    var grammar_id = $('#selected-grammar').val();
    
    if (grammar_id == 'new') {
        initializeTree();
    } else {
        loadGrammarTree(parseInt(grammar_id));
    }
})

$('#save-grammar-btn').click(function() {
    saveGrammarTree();
})

$('#delete-grammar-btn').click(function() {
    deleteGrammarTree($('#selected-grammar').val());
})

loadGrammars();
