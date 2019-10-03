// Global for toggling the enabling of text selection fact creation menu
SELECT_FACT_MENU_ENABLED = false;

function createSelectionProps() {
    var spans = $(".\\[HL\\]").add($("span[title='\\[HL\\]']"));
    // Add hover effect
    spans.hover(function (e) {
        $(this).css("filter", e.type === "mouseenter" ? "brightness(110%)" : "brightness(100%)")
        $(this).css("cursor", "pointer")
    })
    // Add popover system to FACT spans
    tippyForFacts();
    // Add popover system to text search spans
    tippyForText();
    // Add popover system to selection spans
    tippyForSelect();


    function initTippy(doms, tip_content, tip_showOnInit = false) {
        var tippy_instance = tippy(doms,
            {
                content: tip_content,
                interactive: true,
                trigger: 'click',
                showOnInit: tip_showOnInit,
            });
        return tippy_instance
    }

    // Function declarations
    function tippyForFacts(spans) {
        // Select FACT spans
        var spans = $("span[title^='\\[fact']")
        spans.addClass("tippyFactSpan");
        spans = document.querySelectorAll('.tippyFactSpan')
        // Select fact popover template
        var temp = $('.factPopover').clone().removeAttr("style")
        // Create tippy instance
        initTippy(spans, temp.prop('outerHTML'))
        // Create specific content for each span
        Array.prototype.forEach.call(spans, function (span, i) {
            // Display fact name and val
            // Select span data attributes
            var parent = span.parentElement
            var s_data = $(span).data()
            var name = s_data['fact_name']
            var val = span.innerText
            temp.find('.factName').html(name)
            temp.find('.factValue').html(val)
            // Get field 
            var fact_path = parent.className.trim().replace('DtCol_', '')
            // Fact delete button
            var btn_delete = temp.find('.factPopoverDeleteBtn');
            // Attr because click events don't seem to work
            var doc_id = $(examplesTable.row(parent.parentElement).data()[examplesTable.columns()[0].length - 1]).text()
            btn_delete.attr('onclick', `deleteFactSwal("${name}", "${val}", "${doc_id}")`);
            var btn_search = temp.find('.factPopoverSearchBtn');
            btn_search.attr('onclick', `addFactToSearch("${name}","${val}", "${fact_path}")`);
            // Update span tippy content
            span._tippy.setContent(temp.prop('outerHTML'))
        });
    }


    function tippyForText() {
        // Select spans without [FACT] title, add titles with [HL] (for when facts are also present)
        spans = $(".\\[HL\\]").not("span[title~='\\[fact\\]']")
        spans = $(".\\[HL\\]").add("span[title~='\\[HL\\]']").not("span[title^='\\[fact']")
        // Get lens of spans for each parent
        spans.addClass("tippyTextSpan");
        spans = document.querySelectorAll('.tippyTextSpan')
        // Select text popover template
        var temp = $('.textPopover').clone().removeAttr("style")
        // Create tippy instance
        initTippy(spans, temp.prop('outerHTML'))

        Array.prototype.forEach.call(spans, function (span, i) {
            var parent = span.parentElement
            var fact_value = span.innerText;
            var fact_path = parent.className.trim().replace('DtCol_', '')
            // id of the document where fact was derived from, and the document where it will be marked in
            // get doc_id by taking datatables row data last column(_es_id) value
            var doc_id = $(examplesTable.row(parent.parentElement).data()[examplesTable.columns()[0].length - 1]).text()
            var btn = temp.find('.textPopoverSaveBtn');
            btn.attr('onclick', `saveFactFromSelect("${fact_value.replace(/\r?\n|\r/g, '')}", "${fact_path}", "${doc_id}")`);

            // Update span tippy content
            temp.find('.textValue').html(fact_value);
            span._tippy.setContent(temp.prop('outerHTML'));
        });
    }


    function tippyForSelect() {
        $("#examples").find('tbody').find('td').mouseup(function () {
            var selection = window.getSelection();
            // Global SELECT_FACT_MENU_ENABLED for toggling tippyForSelect
            // Check if selection is bigger than 0
            if (SELECT_FACT_MENU_ENABLED && !selection.isCollapsed && selection.toString().trim().length > 1 && selection.toString().trim().length < 300) {
                // Limit selection to the selection start element
                if (selection.anchorNode != selection.focusNode) {
                    selection.setBaseAndExtent(selection.anchorNode, selection.baseOffset, selection.anchorNode, selection.anchorNode.length);
                }
                var range = selection.getRangeAt(0);
                // Tippy for selection
                var textSpan = document.createElement('span');
                textSpan.className = 'selectedText';
                textSpan.appendChild(range.extractContents());
                range.insertNode(textSpan);
                // If selection is not of len 0
                var select_temp = $('.textPopover').clone().removeAttr("style")
                // Create tippy instance
                textTippy = initTippy(textSpan, select_temp.prop('outerHTML'), true)

                var fact_value = selection.toString().trim();
                // Set template value to selected text
                select_temp.find('.textValue').html(fact_value)
                // Get fact_path from td classname, remove _DtCol namesafing
                var fact_path = this.className.trim().replace('DtCol_', '')
                // id of the document where fact was derived from, and the document where it will be marked in
                var doc_id = $(examplesTable.row(this.parentElement).data()[examplesTable.columns()[0].length - 1]).text()
                var btn = select_temp.find('.textPopoverSaveBtn');
                btn.attr('onclick', `saveFactFromSelect("${fact_value.replace(/\r?\n|\r/g, '')}", "${fact_path}", "${doc_id}")`);

                // Update span tippy content
                textSpan._tippy.setContent(select_temp.prop('outerHTML'))
            } else {
                if (typeof textTippy != 'undefined') {
                    removeTextSelections(this, textTippy)
                }
            };
        });
        // Mousedown for removing spans
        $("#examples").find('tbody').find('td').mousedown(function () {
            var selection = window.getSelection();
            if (!selection.isCollapsed && typeof textTippy != 'undefined') {
                removeTextSelections(this, textTippy);
            }
        });
    }


    // Remove selection and tippy instance of selected text
    function removeTextSelections(dom, tip) {
        $(".selectedText").contents().unwrap();
        // If content is unwrapped, but empty element remains
        $(".selectedText").remove();
        // Unwrapping contents breaks strings up into separate strings
        // When its broken up, it breaks selections
        // Normalizing concats them back together
        dom.normalize()
        tip.destroyAll();
    }
}

// Grab fresh input value when called, then save as fact
function saveFactFromSelect(fact_value, fact_field, doc_id) {
    // last() to avoid the dummy template selector
    var fact_name = $('.textName').last().val().trim().toUpperCase();
    var fact_value = fact_value.trim();
    var fact_field = fact_field.trim();
    var doc_id = doc_id.trim();

    if (validateWithFeedback(fact_name, fact_value, fact_field, doc_id)) {
        saveOptionsSwal(fact_name, fact_value, fact_field, doc_id);
    }
}


function saveAsFact(method, match_type, case_sens, fact_name, fact_value, fact_field, doc_id) {
    formElement = new FormData(document.getElementById("filters"));
    formElement.append('fact_name', fact_name);
    formElement.append('fact_value', fact_value);
    formElement.append('fact_field', fact_field);
    formElement.append('doc_id', doc_id);
    formElement.append('method', method);
    formElement.append('match_type', match_type);
    formElement.append('case_sens', case_sens);

    $.ajax({
        url: PREFIX + '/fact_to_doc',
        data: formElement,
        type: 'POST',
        contentType: false,
        processData: false,
        beforeSend: function () {
            const notification = swal.mixin({
                toast: true, position: 'top',
                showConfirmButton: false, timer: 3000
            });

            notification({
                type: 'info',
                title: 'Starting job',
                text: 'Adding fact..'
            })
        },
        success: function (data) {
            const notification = swal.mixin({
                toast: true, position: 'top',
                showConfirmButton: false, timer: 5000
            });


            notification({
                type: 'success',
                title: 'Started Fact Adder task',
                text: 'Check Task Manager Management Tasks to see progress'
            })
        },
        error: function () {
            swal('Error!', 'There was a problem saving as fact!', 'error');
        }
    });
}

async function saveOptionsSwal(fact_name, fact_value, fact_field, doc_id) {
    if (validateWithFeedback(fact_name, fact_value, fact_field, doc_id)) {
        (async function getFormValues() {
            const { value: formValues } = await swal({
                title: `SAVING ${fact_name}: ${fact_value} AS FACT`,
                html:
                    '<form id="saveFactForm">' +
                    '<input type="radio" value="select_only" name="method"> Only the selected text in this document <br>' +
                    '<input type="radio" value="all_in_doc" name="method"> All matches in this document <br>' +
                    '<input type="radio" value="all_in_dataset" name="method"  checked="checked"> All matches in dataset <br>' +
                    '<h5> Select matching method </h5>' +
                    '<input type="radio" value="phrase" name="match_type"> Match as a separate word <br>' +
                    '<input type="radio" value="phrase_prefix" name="match_type"> Match as phrase prefix <br>' +
                    '<input type="radio" value="string" name="match_type"  checked="checked"> Match anywhere in text <br>' +
                    '<h5> Case sensitive? </h5>' +
                    '<input type="radio" value="True" name="case_sens"> Case sensitive <br>' +
                    '<input type="radio" value="False" name="case_sens"  checked="checked"> Case insensitive <br>' +
                    '</form>',
                focusConfirm: true,
                preConfirm: () => {
                    return $('#saveFactForm').serializeArray()
                }
            })

            if (formValues) {
                formValues.forEach(val => {
                    switch (val.name) {
                        case 'method':
                            method = val.value
                            break;
                        case 'match_type':
                            match_type = val.value
                            break;
                        case 'case_sens':
                            case_sens = val.value
                            break;

                        default:
                            break;
                    }
                });
                if (method && match_type && case_sens) {
                    saveAsFact(method, match_type, case_sens, fact_name, fact_value, fact_field, doc_id);
                }
                else {
                    swal('Warning!', 'Method or match type not selected!', 'warning');
                }
            }
        })()
    }
}


function validateWithFeedback(fact_name, fact_value, fact_field, doc_id) {
    if (typeof doc_id == 'undefined' || doc_id == '') {
        swal('Warning!', 'Document id is invalid', 'warning');
        return false;
    }
    if (fact_value.length < 2 || fact_value.length > 300) {
        swal('Warning!', 'Fact length shorter than 2 or longer than 300!', 'warning');
        return false;
    }
    if (fact_name.length > 30 || fact_name == '' || fact_value == '') {
        swal('Warning!', 'Fact name longer than 30 characters, or values are empty!', 'warning');
        return false;
    } else if (fact_field == '_es_id') {
        swal('Warning!', `Saving facts in ${fact_field} not allowed`, 'warning')
        return false;
    }
    return true;
}

async function deleteFactSwal(fact_name, fact_value, doc_id) {
    const inputOptions = new Promise((resolve) => {
        resolve({
            'this_doc': `Delete just in this document (${doc_id})`,
            'all': 'Delete all occurances of this fact in the dataset',
        })
    })

    const { value: method } = await swal({
        title: `Delete fact ${fact_name}:${fact_value}`,
        input: 'radio',
        inputOptions: inputOptions,
        inputValidator: (value) => {
            return !value && 'You need to choose something!'
        }
    })

    if (method) {
        if (method == 'this_doc') {
            deleteFactFromDoc(fact_name, fact_value, doc_id)
        }
        else if (method == 'all') {

            deleteFactArray([{ [fact_name]: fact_value }], source = 'aggs')
        }
    }
}


function toggleTextSelection(checkbox) {
    if ($(checkbox).is(":checked")) {
        SELECT_FACT_MENU_ENABLED = true;
    } else {
        SELECT_FACT_MENU_ENABLED = false;
    }
}
