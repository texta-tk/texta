var PREFIX = LINK_ONTOLOGY_VIEWER;

$(document).ready(function(){
    
    loadConcepts();
    
    $('body').on('click','.concept',function() {
        
        $(".selected").toggleClass("selected");
        $(this).toggleClass("selected");
        
        var xhr = new XMLHttpRequest();

        xhr.onreadystatechange=function() {
            if (xhr.readyState==4 && xhr.status==200) {
                $('body').css('cursor', 'auto');
                var terms = JSON.parse(xhr.responseText)
                empty_div("term_list");
                for (var i = 0; i < terms.length; i++) {
                    createTr(terms[i].term,"tid"+terms[i].id,"term_list","term")
                }
            }
        }
        
        var form_data = new FormData();
        form_data.append("cid",$(this).attr('id').substring(3));
         
        xhr.open("GET",PREFIX + "/get_concept_terms?cid=" + $(this).attr('id').substring(3),false);
        $('body').css('cursor', 'wait');
        xhr.send();
    });

    
    
});

function loadConcepts() {
    var xhr = new XMLHttpRequest();

    xhr.onreadystatechange=function() {
        if (xhr.readyState==4 && xhr.status==200) {
            $('body').css('cursor', 'auto');
            var concepts = JSON.parse(xhr.responseText)
            for (var i = 0; i < concepts.length; i++) {
                createTr(concepts[i].name,"cid"+concepts[i].id,"concept_list","concept")
            }
        }
    }
    
    xhr.open("GET",PREFIX + "/get_concepts",false);
    $('body').css('cursor', 'wait');
    xhr.send();    

}

function remove_concept_tr(response_text) {
    var element = document.getElementById("cid"+response_text);
    element.parentNode.deleteRow(element.sectionRowIndex);
}

function remove_term_tr(response_text) {
    var element = document.getElementById("tid"+response_text);
    element.parentNode.deleteRow(element.sectionRowIndex);
}

function createTr(name,id,container_id,class_name,type) {
    var trElement = document.createElement("tr");
    var tdElement1 = document.createElement("td");
    var tdElement2 = document.createElement("td");
    var aElement = document.createElement("a");
    var imgElement = document.createElement("img");
    
    if (id) { 
        trElement.id = id;
    }
    
    if (class_name) {
        trElement.className = class_name;
    }

    aElement.href = "javascript:void(0)";
    aElement.onclick = function() {
        async_get_query(PREFIX + '/delete_' + class_name + '?id=' + id.substring(3),class_name == "term" ? remove_term_tr : remove_concept_tr);
    };
    
    imgElement.src = STATIC_URL + "img/delete.png";
    
    aElement.appendChild(imgElement);
    
    tdElement1.appendChild(document.createTextNode(name));
    tdElement2.appendChild(aElement);
    trElement.appendChild(tdElement1);
    trElement.appendChild(tdElement2);
    document.getElementById(container_id).appendChild(trElement);
    
}

function empty_div(id) {
    var div = document.getElementById(id);
    
    while (div.firstChild) {
        div.removeChild(div.firstChild);
    }
}