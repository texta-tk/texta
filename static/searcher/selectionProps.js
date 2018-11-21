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
                // Set template value to selected text
                temp.find('.textValue').html(fact_val)
                // Get fact_path from td classname, remove _DtCol namesafing
                var fact_path = this.className.trim().replace('DtCol_', '')
                // id of the document where fact was derived from, and the document where it will be marked in
                var doc_id = $(examplesTable.row(this.parentElement).data()[examplesTable.columns()[0].length - 1]).text()
                // add click event for save button in tippy
                $(document).on('click', '.textPopoverSaveBtn', function () {
                    saveFactFromSelect(fact_val, fact_path, doc_id);
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
            var btn = temp.find('.textPopoverSaveBtn');
            btn.attr('onclick', `saveFactFromSelect("${fact_val}", "${fact_path}", "${doc_id}")`);

            // Update span tippy content
            temp.find('.textValue').html(fact_val);
            span._tippy.setContent(temp.prop('outerHTML'));
        });
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
function saveFactFromSelect(fact_value, fact_field, doc_id) {
    // last() to avoid the dummy template selector
    fact_name = $('.textName').last().val().trim().toUpperCase();
    fact_value = fact_value.trim();
    fact_field = fact_field.trim();
    doc_id = doc_id.trim();
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

            factsAdded = data.fact_count
            status = data.status
            type = ''
            title = ''
            switch(status) {
                case 'success':
                    type = 'success';
                    title = 'Adding fact successful!';
                    text = `${factsAdded} facts like ${fact_name}: ${fact_value} have been added.`;
                    break
                case 'no_hits':
                    type = 'warning';
                    title = 'Could not find given facts';
                    text = `Facts like ${fact_name}: ${fact_value} have not been added.`;
                    break
                case 'scrolling_error':
                    type = 'warning'
                    title = 'A problem occured whilst adding facts'
                    text = `${factsAdded} facts like ${fact_name}: ${fact_value} were added.`;
                    break;
                default:
                    type = 'warning'
                    title = 'A problem occured whilst adding facts'
                    text = `${factsAdded} facts like ${fact_name}: ${fact_value} were added.`;
            }

            notification({
                type: type,
                title: title,
                text: text
            })
        },
        error: function () {
            swal('Error!', 'There was a problem saving as fact!', 'error');
        }
    });
}

async function saveOptionsSwal(fact_name, fact_value, fact_field, doc_id) {
    // if (validateWithFeedback(fact_name, fact_value, fact_field, doc_id)) {
    //     swal.mixin({
    //         confirmButtonText: 'Next &rarr;',
    //         showCancelButton: true,
    //         progressSteps: ['1', '2', '3', '4']
    //     }).queue([
    //         {
    //             title: `Are you sure you want to save this as a fact?`,
    //             html: `<b>${fact_name}: ${fact_value}</b> will be saved as a fact!`,
    //             type: 'question',
    //             showCancelButton: true,
    //             confirmButtonColor: '#73AD21',
    //             cancelButtonColor: '#d33',
    //             confirmButtonText: 'Yes'
    //         },
    //         {
    //             title: 'Select saving method',
    //             input: 'radio',
    //             inputOptions: {
    //                 'select_only': 'Only the selected text in this document',
    //                 'all_in_doc': 'All matches in this document',
    //                 'all_in_dataset': 'All matches in dataset'
    //             }
    //         },
    //         {
    //             title: 'Select matching method',
    //             input: 'radio',
    //             inputOptions: {
    //                 'phrase': 'Match as a separate word',
    //                 'phrase_prefix': 'Match as phrase prefix',
    //                 'string': 'Match anywhere in text'
    //             },
    //         },
    //         {
    //             title: 'Case sensitive?',
    //             text: 'Save similar facts separately based on case',
    //             input: 'radio',
    //             inputOptions: {
    //                 'True': 'Case sensitive',
    //                 'False': 'Case insensitive',
    //             },
    //         }
    //     ]).then((result) => {
    //         if (result.value) {
    //             method = result.value[1]
    //             match_type = result.value[2]
    //             case_sens = result.value[3]
    //             if (method && match_type) {
    //                 saveAsFact(method, match_type, case_sens, fact_name.toUpperCase(), fact_value, fact_field, doc_id);
    //             }
    //             else {
    //                 swal('Warning!', 'Method or match type not selected!', 'warning');
    //             }
    //         }
    //     })
    // }


    if (validateWithFeedback(fact_name, fact_value, fact_field, doc_id)) {

        (async function backAndForth() {
            const steps = ['1', '2', '3'];
            const question = [`SAVING ${fact_name}: ${fact_value} AS FACT`, 'Select matching method', 'Case sensitive?'];
            const values = [
                {
                    'select_only': 'Only the selected text in this document',
                    'all_in_doc': 'All matches in this document',
                    'all_in_dataset': 'All matches in dataset'
                },
                {
                    'phrase': 'Match as a separate word',
                    'phrase_prefix': 'Match as phrase prefix',
                    'string': 'Match anywhere in text'
                },
                {
                    'True': 'Case sensitive',
                    'False': 'Case insensitive'
                }];

            let currentStep;
            swal.setDefaults({
                confirmButtonText: 'Forward',
                cancelButtonText: 'Back',
                progressSteps: steps,
                input: 'radio'
            })

            for (currentStep = 0; currentStep < steps.length;) {
                const result = await swal({
                    title: question[currentStep],
                    inputOptions: values[currentStep],
                    showCancelButton: true,
                    currentProgressStep: currentStep
                });

                if (result.value) {
                    values[currentStep] = result.value
                    currentStep++;
                    if (currentStep == steps.length) {
                        swal.resetDefaults();
                        method = values[0]
                        match_type = values[1]
                        case_sens = values[2]
                        if (method && match_type && case_sens) {
                            saveAsFact(method, match_type, case_sens, fact_name, fact_value, fact_field, doc_id);
                        }
                        else {
                            swal('Warning!', 'Method or match type not selected!', 'warning');
                        }
                        break
                    }
                } else if (result.dismiss === 'cancel') {
                    currentStep--;
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
    if (fact_value.length < 2 || fact_value.length  > 300) {
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
