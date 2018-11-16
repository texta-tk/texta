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

    // Function declarations
    function tippyForFacts(spans) {
        // Select FACT spans
        var spans = $("span[title~='\\[fact\\]']")
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
            var s_data = $(span).data()
            var name = s_data['fact_name']
            var val = span.innerText
            temp.find('.factName').html(name)
            temp.find('.factValue').html(val)
            // Fact delete button
            var btn_delete = temp.find('.factPopoverDeleteBtn');
            // Attr because click events don't seem to work
            btn_delete.attr('onclick', `deleteFactArray([{"${name}":"${val}"}], alert=true)`);
            var btn_search = temp.find('.factPopoverSearchBtn');
            btn_search.attr('onclick', `addFactToSearch("${name}","${val}")`);
            // Update span tippy content
            span._tippy.setContent(temp.prop('outerHTML'))
        });
    }


    function tippyForSelect() {
        $("#examples").find('tbody').find('td').mouseup(function () {
            var selection = window.getSelection();
            // Check if selection is bigger than 0
            if (!selection.isCollapsed && selection.toString().trim().length > 1 && selection.toString().trim().length < 300) {
                // Limit selection to the selection start element
                if (selection.baseNode != selection.focusNode) {
                    selection.setBaseAndExtent(selection.baseNode, selection.baseOffset, selection.baseNode, selection.baseNode.length);
                }
                var range = selection.getRangeAt(0);
                // Tippy for selection
                var textSpan = document.createElement('span');
                textSpan.className = 'selectedText';
                textSpan.appendChild(range.extractContents());
                range.insertNode(textSpan);
                // If selection is not of len 0
                var temp = $('.textPopover').clone().removeAttr("style")
                // Create tippy instance
                textTippy = initTippy(textSpan, temp.prop('outerHTML'), true)

                var fact_val = selection.toString().trim();
                var loc_spans = getLocSpans(this, fact_val)
                // Set template value to selected text
                temp.find('.textValue').html(fact_val)
                // Get fact_path from td classname, remove _DtCol namesafing
                var fact_path = this.className.trim().replace('DtCol_', '')
                // id of the document where fact was derived from, and the document where it will be marked in
                var doc_id = $(examplesTable.row(this.parentElement).data()[examplesTable.columns()[0].length - 1]).text()
                // add click event for save button in tippy
                $(document).on('click', '.textPopoverSaveBtn', function () {
                    saveFactFromSelect(fact_val, fact_path, [loc_spans], doc_id);
                });

                // Update span tippy content
                textSpan._tippy.setContent(temp.prop('outerHTML'))
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


    function tippyForText() {
        // Select spans without [FACT] title, add titles with [HL] (for when facts are also present)
        spans = $(".\\[HL\\]").not("span[title~='\\[fact\\]']")
        spans = $(".\\[HL\\]").add("span[title~='\\[HL\\]']").not("span[title~='\\[fact\\]']")
        // Get lens of spans for each parent
        spans.addClass("tippyTextSpan");
        spans = document.querySelectorAll('.tippyTextSpan')
        // Select text popover template
        var temp = $('.textPopover').clone().removeAttr("style")
        // Create tippy instance
        initTippy(spans, temp.prop('outerHTML'))

        Array.prototype.forEach.call(spans, function (span, i) {
            var parent = span.parentElement
            var fact_val = span.innerText;
            var fact_path = parent.className.trim().replace('DtCol_', '')
            // id of the document where fact was derived from, and the document where it will be marked in
            // get doc_id by taking datatables row data last column(_es_id) value
            var doc_id = $(examplesTable.row(parent.parentElement).data()[examplesTable.columns()[0].length - 1]).text()
            var loc_spans = getLocSpans(parent, fact_val)
            var btn = temp.find('.textPopoverSaveBtn');
            btn.attr('onclick', `saveFactFromSelect("${fact_val}", "${fact_path}", [${loc_spans}]," ${doc_id}")`);

            // Update span tippy content
            temp.find('.textValue').html(fact_val);
            span._tippy.setContent(temp.prop('outerHTML'));
        });
    }


    function getLocSpans(parent, val) {
        loc_span_start = parent.innerText.indexOf(val);
        loc_spans = [loc_span_start, loc_span_start + val.length];
        return loc_spans
    }

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
}

// Grab fresh input value when called, then save as fact
function saveFactFromSelect(fact_value, fact_field, fact_span, doc_id) {
    // last() to avoid the dummy template selector
    fact_name = $('.textName').last().val();
    if (validateWithFeedback(fact_name.toUpperCase().trim(), fact_value.trim(), fact_field.trim(), fact_span, doc_id.trim())) {
        saveOptionsSwal(fact_name.toUpperCase().trim(), fact_value.trim(), fact_field.trim(), fact_span, doc_id.trim());
        // saveAsFact(fact_name.toUpperCase().trim(), fact_value.trim(), fact_field.trim(), fact_span, doc_id.trim());
    }
}


function saveAsFact(method, fact_name, fact_value, fact_field, fact_span, doc_id) {
    if (validateWithFeedback(fact_name, fact_value, fact_field, fact_span, doc_id)) {
        var title = '';
        var html = '';
        switch(method) {
            case 'select_only':
                title = 'Are you sure you want to save this as a fact?';
                html = `The fact <b>${fact_name}: ${fact_value}</b> will be added as a fact to field <b>${fact_field}</b>`;
                break;
            case 'all_in_doc':
                title = 'Are you sure you want to save all exact matches of selected value in this document?';
                html = `The fact <b>${fact_name}: ${fact_value}</b> will be added as a fact to field <b>${fact_field}</b> for <b> all matches in this document </b>`;
                break;
            case 'all_in_dataset':
                title = 'Are you sure you want to save all exact matches of selected value in this dataset?';
                html = `The fact <b>${fact_name}: ${fact_value}</b> will be added as a fact to field <b>${fact_field}</b> for <b> all matches in the dataset </b>`;
                break;
            default:
                swal('Warning!', 'No saving method selected!', 'warning');
                return false;
        }
        swal({
            title: title,
            html: html,
            type: 'question',
            showCancelButton: true,
            confirmButtonColor: '#73AD21',
            cancelButtonColor: '#d33',
            confirmButtonText: 'Yes'
        }).then((result) => {
            if (result.value) {
                formElement = new FormData(document.getElementById("filters"));
                formElement.append('fact_name', fact_name);
                formElement.append('fact_value', fact_value);
                formElement.append('fact_field', fact_field);
                formElement.append('fact_span', fact_span);
                formElement.append('doc_id', doc_id);

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
                    success: function () {
                        const notification = swal.mixin({
                            toast: true, position: 'top',
                            showConfirmButton: false, timer: 3000
                        });

                        notification({
                            type: 'success',
                            title: 'Adding fact successful!',
                            text: `Fact ${fact_name}: ${fact_value} has been added.`
                        })
                    },
                    error: function () {
                        swal('Error!', 'There was a problem saving as fact!', 'error');
                    }
                });
            }
        });
    }
}

async function saveOptionsSwal(fact_name, fact_value, fact_field, fact_span, doc_id) {
    // inputOptions can be an object or Promise
    const inputOptions = new Promise((resolve) => {
        resolve({
            'select_only': 'Only selected value in this document',
            'all_in_doc': 'All exact matches in this document',
            'all_in_dataset': 'All exact matches in dataset'
        })
    })

    const { value: save_method } = await swal({
        title: 'Select saving method',
        input: 'radio',
        inputOptions: inputOptions,
        inputValidator: (value) => {
            return !value && 'You need to choose something!'
        }
    })

    if (save_method) {
        swal({ html: 'You selected: ' + save_method })
            saveAsFact(save_method, fact_name.toUpperCase().trim(), fact_value.trim(), fact_field.trim(), fact_span, doc_id.trim());
    }
}

function validateWithFeedback(fact_name, fact_value, fact_field, fact_span, doc_id) {
    if (typeof doc_id == 'undefined' || doc_id == '') {
        swal('Warning!', 'Document id is invalid', 'warning');
        return false;
    }
    if ((fact_span[1] - fact_span[0]) < 2 || (fact_span[1] - fact_span[0]) > 300) {
        swal('Warning!', 'Fact length shorter than 2 or longer than 300!', 'warning');
        return false;
    }
    if (fact_name.length > 15 || fact_name == '' || fact_value == '') {
        swal('Warning!', 'Fact name longer than 15 characters, or values are empty!', 'warning');
        return false;
    } else if (fact_field == '_es_id') {
        swal('Warning!', `Saving facts in ${fact_field} not allowed`, 'warning')
        return false;
    }
    return true;
}