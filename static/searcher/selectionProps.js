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
            s_data = $(span).data()
            name = s_data['fact_name']
            val = span.innerText
            temp.find('.factName').html(name)
            temp.find('.factValue').html(val)
            // Fact delete button
            btn_delete = temp.find('.factPopoverDeleteBtn');
            // Attr because click events don't seem to work
            btn_delete.attr('onclick', `deleteFactArray([{"${name}":"${val}"}], alert=true)`);
            btn_search = temp.find('.factPopoverSearchBtn');
            btn_search.attr('onclick', `addFactToSearch("${name}","${val}")`);
            // Update span tippy content
            span._tippy.setContent(temp.prop('outerHTML'))
        });
    }


    function tippyForSelect() {
        $("#examples").find('tbody').find('td').mouseup(function () {
            var selection = window.getSelection();
            // Check if selection is bigger than 0
            if (!selection.isCollapsed) {
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
                temp = $('.textPopover').clone().removeAttr("style")
                // Create tippy instance
                textTippy = initTippy(textSpan, temp.prop('outerHTML'), true)

                var fact_val = selection.toString();
                loc_spans = getLocSpans(this, fact_val)
                // Set template value to selected text
                temp.find('.textValue').html(fact_val)
                // Save as fact button
                btn = temp.find('.textPopoverSaveBtn');

                // Get fact_path from td classname, remove _DtCol namesafing
                fact_path = this.className.trim().replace('DtCol_', '')
                // id of the document where fact was derived from, and the document where it will be marked in
                doc_id = $(examplesTable.row(this.parentElement).data()[examplesTable.columns()[0].length - 1]).text()
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
            if (!selection.isCollapsed) {
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
            parent = span.parentElement
            fact_val = span.innerText;
            fact_path = parent.className.trim().replace('DtCol_', '')
            // id of the document where fact was derived from, and the document where it will be marked in
            // get doc_id by taking datatables row data last column(_es_id) value
            doc_id = $(examplesTable.row(parent.parentElement).data()[examplesTable.columns()[0].length - 1]).text()
            loc_spans = getLocSpans(parent, fact_val)
            btn = temp.find('.textPopoverSaveBtn');
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

    function initTippy(doms, tip_content, tip_showOnInit=false) {
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
    saveAsFact(fact_name.toUpperCase().trim(), fact_value.trim(), fact_field.trim(), fact_span, doc_id.trim());
}

function saveAsFact(fact_name, fact_value, fact_field, fact_span, doc_id) {
    if (fact_name.length > 15 || fact_name == '' || fact_value == '') {
        swal('Warning!', 'Fact name longer than 15 characters, or values are empty!', 'warning');
    } else {
        swal({
            title: 'Are you sure you want to save this as a fact?',
            html: `The fact <b>${fact_name}: ${fact_value}</b> will be added as a fact to field <b>${fact_field}</b>`,
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
                    beforeSend: function() {
                        const notification = swal.mixin({
                            toast: true, position: 'top',
                            showConfirmButton: false, timer: 3000});

                        notification({
                            type: 'info',
                            title: 'Starting job',
                            text: 'Adding fact to dataset..'
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


/* Looks like method is not compatible with just text search
fact_span = getParentChildInd(spans, parent, span, lens);
function getParentChildInd(original, parent, child, lens) {
    parents = Array.prototype.slice.call($(original).parent())
    parent_ind = parents.indexOf(parent)
    child_ind = Array.prototype.slice.call(parent.children).indexOf(child)
    return lens[parent_ind][child_ind]
}

lens = countSpanLens(spans)
function countSpanLens(spans) {
    parents = spans.parent()
    lens = []
    Array.prototype.forEach.call(parents, function (parent, i) {
        // 0 so adding as cumsum on first iter wouldn't return NaN
        parent_lens = [0]
        Array.prototype.forEach.call(parent.children, function (span, i) {
            // append to array, add to cumulative sum
            parent_lens = [...parent_lens, parent_lens[parent_lens.length-1] + span.innerText.length]
        });
        // remove first dummy 0 value
        parent_lens.shift()
        lens = [...lens, parent_lens]
    });
    return lens;
    // For each parent create an array entry, that contains span lens in cumsum format, eg [[5, 10, ]]
    // Get lens of all child spans, maybe cumsum
    // Get index of the selected parent and in it span, match it to its len value,
    // Start indexof from that len value
}
*/
