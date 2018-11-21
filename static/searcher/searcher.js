var PREFIX = LINK_SEARCHER
var examplesTable
var layers = ['text', 'lemmas', 'facts']
var removed_facts = []

$(document).ready(function () {
    change_agg_field(1)

    $('#agg_daterange_from_1').datepicker({
        format: 'yyyy-mm-dd',
        startView: 2,
        autoclose: true
    })
    $('#agg_daterange_to_1').datepicker({
        format: 'yyyy-mm-dd',
        startView: 2,
        autoclose: true
    })

    $(document.body).on('click', 'a.toggle-visibility', function (e) {
        e.preventDefault()

        $(this).toggleClass('feature-invisible')

        // Get the column API object
        var column = examplesTable.column($(this).attr('data-column'))

        // Toggle the visibility
        column.visible(!column.visible())

        examplesTable.columns.adjust()

        var dataset = $('#dataset').val()
        var mapping = $('#mapping').val()

        var hiddenFeatures = localStorage.getCacheItem('hiddenFeatures_' + dataset + '_' + mapping)
        if (!hiddenFeatures) {
            hiddenFeatures = {}
        }

        if ($(this).hasClass('feature-invisible')) {
            hiddenFeatures[$(this).attr('data-column')] = true
        } else {
            if (hiddenFeatures.hasOwnProperty($(this).attr('data-column'))) {
                delete hiddenFeatures[$(this).attr('data-column')]
            }
        }
        localStorage.setCacheItem(('hiddenFeatures_' + dataset + '_' + mapping), hiddenFeatures, {
            months: 1
        })
    })

    $('#n_char').bootstrapSlider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })
    $('#n_char_cluster').bootstrapSlider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#n_clusters').bootstrapSlider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#n_samples').bootstrapSlider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#n_keywords').bootstrapSlider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#n_features').bootstrapSlider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#n_agg_size_1').bootstrapSlider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#n_agg_size_2').bootstrapSlider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })

    $('#nFactGraphSize').bootstrapSlider({
        formatter: function (value) {
            return 'Current value: ' + value
        }
    })
})

function get_query () {
    var formElement = document.getElementById('filters')
    var request = new XMLHttpRequest()

    request.onreadystatechange = function () {
        if (request.readyState == 4 && request.status == 200) {
            if (request.responseText.length > 0) {
                var query_container = $('#query-modal-content')
                query_container.html(JSON.stringify(JSON.parse(request.responseText)))
            }
        }
    }

    request.open('POST', PREFIX + '/get_query')
    request.send(new FormData(formElement), true)
}

function lookup (fieldFullId, fieldId, action, lookup_types) {
    var content = $('#' + fieldFullId).val()

    if (fieldFullId.match('^fact_constraint_val_')) {
        var factName = $('#fact_txt_' + fieldId.slice(0, -4)).val()
    } else {
        var factName = ''
    }

    var lookup_data = {
        content: content,
        action: action,
        lookup_types: lookup_types,
        key_constraints: factName
    }
    $.post(PREFIX + '/autocomplete', lookup_data, function (data) {
        if (data.length > 0) {
            var suggestions_container = $('#suggestions_' + fieldId)
            suggestions_container.empty()

            process_suggestions(data, suggestions_container, fieldId, lookup_types)
            if (suggestions_container.html()) {
                $('#suggestions_' + fieldId).show()
            }
        } else {
            $('#suggestions_' + fieldId).hide()
        }
    })
}

function process_suggestions (suggestions, suggestions_container, field_id, lookup_types) {
    var suggestions = JSON.parse(suggestions)

    $.each(suggestions, function (lookup_type, lookup_suggestions) {
        if (lookup_suggestions.length > 0) {
            var li = $('<div/>')
                .text(lookup_type)
                .css('font-weight', 'Bold')
                .appendTo(suggestions_container)

            $.each(lookup_suggestions, function (i) {
                var li = $('<li/>')
                    .addClass('list-group-item')
                    .addClass('pointer')
                    .attr('onclick', "insert('" + lookup_suggestions[i]['resource_id'] + "','" + field_id + "','" + lookup_suggestions[i]['entry_text'] + "','" + lookup_type + "')")
                    .html(lookup_suggestions[i]['display_text'])
                    .appendTo(suggestions_container)
            })
        }
    })
}

function insert (resource_id, suggestionId, descriptive_term, lookup_type) {
    if (resource_id) {
        if (lookup_type == 'CONCEPT') {
            suggestion_prefix = '@C'
        } else if (lookup_type == 'LEXICON') {
            suggestion_prefix = '@L'
        }

        $('#field_' + suggestionId + ' #match_txt_' + suggestionId).val(function (index, value) {
            return value.replace(/[^(\n)]*$/, '')
        })
        $('#field_' + suggestionId + ' #match_txt_' + suggestionId).val($('#field_' + suggestionId + ' #match_txt_' + suggestionId).val() + suggestion_prefix + resource_id + '-' + descriptive_term + '\n')
        $('#field_' + suggestionId + ' #match_txt_' + suggestionId).focus()
    } else {
        if (lookup_type == 'TEXT') {
            $('#field_' + suggestionId + ' #match_txt_' + suggestionId).val(function (index, value) {
                return value.replace(/[^(\n)]*$/, '')
            })
            $('#field_' + suggestionId + ' #match_txt_' + suggestionId).val($('#field_' + suggestionId + ' #match_txt_' + suggestionId).val() + descriptive_term + '\n')
        }
        if (lookup_type == 'FACT_NAME') {
            var separatorIdx = suggestionId.indexOf('_')
            if (separatorIdx > -1) {
                var fieldId = suggestionId.substring(0, separatorIdx)
            } else {
                var fieldId = suggestionId
            }

            if (separatorIdx > -1) {
                $('#field_' + fieldId + ' #fact_txt_' + suggestionId).val(descriptive_term)
            } else {
                $('#field_' + fieldId + ' #fact_txt_' + suggestionId).val(function (index, value) {
                    return value.replace(/[^(\n)]*$/, '')
                })
                $('#field_' + fieldId + ' #fact_txt_' + suggestionId).val($('#field_' + suggestionId + ' #fact_txt_' + suggestionId).val() + descriptive_term + '\n')
            }
        }
        if (lookup_type == 'FACT_VAL') {
            var suggestionIdPrefix = suggestionId.replace('_val', '')
            $('#fact_constraint_val_' + suggestionIdPrefix).val(descriptive_term)
        }
    }
}

function remove_fact_rule (rule_id) {
    $('#fact_val_rule_' + rule_id).remove()
}

function select_all_fields () {
    if ($('#check_all_mapping_fields').prop('checked') == true) {
        $.each($("[name^='mapping_field_']"), function () {
            $(this).prop('checked', true)
        })
    } else {
        $.each($("[name^='mapping_field_']"), function () {
            $(this).prop('checked', false)
        })
    }
}

function hide (id) {
    var separatorIdx = id.indexOf('_')
    if (separatorIdx > -1) {
        var fieldId = id.substring(0, separatorIdx)
    } else {
        var fieldId = id
    }
    $('#field_' + fieldId + ' #suggestions_' + id).mouseleave(function () {
        if (!$('#field_' + fieldId + ' #suggestions_' + id).is(':hover')) {
            $('#field_' + fieldId + ' #suggestions_' + id).hide()
        }
    })
    // setTimeout(function() {
    //         if(!$("#field_"+fieldId+" #suggestions_"+id).is(":hover")) {
    //             $("#field_"+fieldId+" #suggestions_"+id).hide();
    //         }
    //         else{
    //         }
    //     }, 1000);
    // });
}

function remove_field (id) {
    $('#' + id).remove()
}

function query () {
    var formElement = document.getElementById('filters')
    var request = new XMLHttpRequest()
    request.onreadystatechange = function () {
        if (request.readyState == 4 && request.status == 200) {
            $('#right').html(request.responseText)
            examplesTable = $('#examples').DataTable({
                'bAutoWidth': false,
                'lengthMenu': [
                    [10, 25, 50, -1],
                    [10, 25, 50, 'All']
                ],
                'deferRender': true,
                'scrollY': '80vh',
                'bServerSide': true,
                'processing': true,
                'sAjaxSource': PREFIX + '/table_content',
                'dom': "<'#top-part''row'<'col-xs-6'l><'col-xs-6'i>rp>t",
                'sServerMethod': 'POST',
                'fnServerParams': function (aoData) {
                    aoData.push({
                        'name': 'filterParams',
                        'value': data = JSON.stringify($('#filters').serializeArray())
                    })
                },

                'oLanguage': {
                    'sProcessing': 'Loading...'
                },
                'fnInitComplete': function () {
                    $('.dataTables_scrollHead').css('overflow-x', 'auto')
                    // Sync THEAD scrolling with TBODY
                    $('.dataTables_scrollHead').on('scroll', function () {
                        $('.dataTables_scrollBody').scrollLeft($(this).scrollLeft())
                    })
                },
                'stateSave': true,
                'stateSaveParams': function (settings, data) {
                    data.start = 0
                },
                'stateLoadParams': function (settings, data) {
                    /*  because state has the last saved state of the table, not the current one then we can check
                    if the selected datasets were changed and if extra columns were added, removed,
                    if they were then select all (also did this in previous version, with buttons) */
                    if ($('#examples').DataTable().columns().nodes().length != data.columns.length) {
                        $('#toggle-column-select').selectpicker('selectAll')
                    } else {
                        $('#toggle-column-select').selectpicker('deselectAll')
                        for (var i = 0, ien = data.columns.length; i < ien; i++) {
                            if (data.columns[i].visible) {
                                /* sync select with the table */
                                updateSelectColumnFilter(i)
                            }
                        }
                    }
                    $('#toggle-column-select').selectpicker('refresh')
                },
                'scrollX': true
            })

            initColumnSelectVisiblity(examplesTable)

            var dataset = $('#dataset').val()
            var mapping = $('#mapping').val()
            var div = $('#top-part')
            var button = $('.toggle-column-select-wrapper')
            button.appendTo(div)

            loadUserPreference(dataset, mapping)
            $('#actions-btn').removeClass('invisible')
            $('#export-examples-modal').removeClass('invisible')
            $('#export-aggregation-modal').addClass('invisible')
        }
    }

    request.open('POST', PREFIX + '/table_header')
    request.send(new FormData(formElement))
}

function initColumnSelectVisiblity (examplesTable) {
    var $select = $('#toggle-column-select')
    $select.selectpicker({
        style: 'btn btn-default',
        maxWidth: 150
    })
    $('#right .bs-deselect-all').on('click', function () {
        examplesTable.columns().visible(false)
    })
    $('#right .bs-select-all').on('click', function () {
        examplesTable.columns().visible(true)
    })
    $select.on('changed.bs.select', function (e, clickedIndex, newValue, oldValue) {
        /* if (select all / deselect) buttons are not the callers */
        if (newValue != null) {
            /* clickedindex same as column index anyway, cause same order, so dont need to use this */
            /* var selected = $(this).find('option').eq(clickedIndex).val() */
            examplesTable.column(clickedIndex).visible(!examplesTable.column(clickedIndex).visible())
        }
    })
    /* if its the users first time loading, then there is no state saved so just select all */
    if (examplesTable.state.loaded() == null) {
        $select.selectpicker('selectAll')
    }
    $select.selectpicker('refresh')
}

function updateSelectColumnFilter (idx) {
    /* selects content is layed out the same order as the columns list, child starts at 1 instead of 0, so just add 1 */
    $(`#toggle-column-select :nth-child(${idx + 1})`).prop('selected', true)
}
function accept_document (id) {
    $('#docs').val($('#docs').val() + id + '\n')
    $('#row_' + id).remove()
}

function reject_document (id) {
    $('#docs_rejected').val($('#docs_rejected').val() + id + '\n')
    $('#row_' + id).remove()
}

function aggregate () {
    var container = $('#right')
    container.empty()
    container.append('Loading...')

    var formElement = document.getElementById('filters')
    var request = new XMLHttpRequest()
    request.onreadystatechange = function () {
        if (request.readyState == 4 && request.status == 200) {
            if (request.responseText.length > 0) {
                displayAgg(JSON.parse(request.responseText))
                $('#actions-btn').removeClass('invisible')
                $('#export-examples-modal').addClass('invisible')
                $('#export-aggregation-modal').removeClass('invisible')
            }
        }
    }
    request.open('POST', PREFIX + '/aggregate')
    request.send(new FormData(formElement), true)
}

function factGraph () {
    var container = $('#right')
    container.empty()
    container.append('Loading...')

    var formElement = document.getElementById('filters')
    var request = new XMLHttpRequest()

    request.onreadystatechange = function () {
        if (request.readyState == 4 && request.status == 200) {
            $('#right').html(request.responseText)
        }
    }
    request.open('POST', PREFIX + '/fact_graph')
    request.send(new FormData(formElement), true)
}

function displayAgg (response) {
    var data = response
    var container = $('#right')
    container.empty()

    var string_container = $("<div id='string_agg_container'></div>")
    var chart_container = $("<div id='daterange_agg_container'></div>")

    container.append(chart_container)
    container.append(string_container)

    for (var i in data) {
        if (data.hasOwnProperty(i)) {
            if (data[i].type == 'daterange') {
                drawTimeline(data[i])
            } else if (data[i].type == 'string') {
                drawStringAggs(data[i])
            } else if (data[i].type == 'fact') {
                drawStringAggs(data[i], type = 'fact')
            } else if (data[i].type == 'fact_str_val') {
                drawStringAggs(data[i])
            } else if (data[i].type == 'fact_num_val') {
                drawStringAggs(data[i])
            }
        }
    }
}

function drawTimeline (data) {
    var timeline_children_container = $('<div></div>')

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
        labels: data.labels

    }).on('click', function (i, row) {
        var children_data = data.children[row.date]
        show_children(children_data, row.date, timeline_children_container)
    })

    $('#right').append(timeline_children_container)
}

function show_children (data, date, timeline_children_container) {
    timeline_children_container.empty()
    $.each(data, function (i, data_list) {
        var responseContainers = [$("<div style='float: left; padding-left: 20px;'></div>")]

        var tbody = $('<tbody></tbody>')

        var valTables = []

        $.each(data_list.data, function (j, row) {
            var row_container = $('<tr><td>' + row.val + '</td><td>' + row.key + '</td></tr>')

            var valsTbody = $('<tbody></tbody>')
            var valsTable = $("<table id='" + i + '-' + row.key + "-table' class='table table-striped table-hover fact-val-table-" + i + "' style='display: none;'></table>")
            valsTable.append("<thead><th colspan='2'>&nbsp;</th></head>")

            if (!row.hasOwnProperty('children')) {
                row.children = []
            }

            $.each(row.children, function (k, child_row) {
                valsTbody.append($('<tr><td>' + child_row.val + '</td><td>' + child_row.key + '</td></tr>'))
            })

            row_container.click(function () {
                $('.fact-val-table-' + i).hide()
                $('#' + i + '-' + row.key + '-table').show()
            })

            valsTable.append(valsTbody)

            if (row.children.length > 0) {
                row_container.addClass('pointer')

                var responseContainer = $("<div style='float: left; padding-left: 20px;'></div>")
                responseContainer.append(valsTable)
                responseContainers.push(responseContainer)
            }

            tbody.append(row_container)
        })

        var table = $("<table class='table table-striped table-hover'></table>")
        table.append("<thead><th colspan='2'>" + data_list.label + '</th></head>')
        table.append(tbody)
        responseContainers[0].append(table)

        $.each(responseContainers, function (i, container) {
            timeline_children_container.append(container)
        })
    })
}

function drawStringAggs (data, type = null) {
    var response_container = $("<div style='float: left; padding-left: 20px;'></div>")
    var table_container = $("<div style='float: left'></div>")
    var children_container = $("<div style='background-color: white; float: left; min-width: 200px;' class='hidden'></div>")
    var grandchildren_container = $("<div id='grandchildren_container' style='background-color: white; float: left; min-width: 200px;' class='hidden'></div>")

    var tbody = $('<tbody></tbody>')

    $.each(data.data, function (i, row) {
        if (row.children.length > 0) {
            var row_container = $('<tr><td>' + row.val + '</td><td>' + row.key + "</td><td><span class='glyphicon glyphicon-menu-right'></span></td></tr>")
            row_container.click(function () {
                show_string_children(row.children, children_container, grandchildren_container, row.key, type = type)
            })
            row_container.addClass('pointer')
        } else {
            var row_container = $('<tr><td>' + row.val + '</td><td>' + row.key + '</td><td></td></tr>')
        }
        tbody.append(row_container)
    })

    var table = $("<table class='table table-striped table-hover'></table>")
    table.append("<thead><th colspan='2'>Field #1</th></head>")
    table.append(tbody)

    table_container.append(table)

    response_container.append("<div class='row text-center'><h3>" + data.label + '</h3></div>')
    response_container.append(table_container)
    response_container.append(children_container)
    response_container.append(grandchildren_container)

    $('#string_agg_container').append(response_container)
}

var selectedFactCheckboxes = []

function factDeleteCheckbox (checkbox) {
    inArray = false
    if (!selectedFactCheckboxes.length > 0) {
        selectedFactCheckboxes.push(checkbox)
    } else {
        i = 0
        while (!inArray && i < selectedFactCheckboxes.length) {
            if (selectedFactCheckboxes[i].name == checkbox.name) {
                selectedFactCheckboxes.splice(i, 1)
                inArray = true
            }
            i++
        }
        if (!inArray) {
            selectedFactCheckboxes.push(checkbox)
        }
    }
}

function deleteFactsViaCheckboxes (checkboxes) {
    factArray = []
    for (var i = 0; i < checkboxes.length; i++) {
        fact = JSON.parse(checkboxes[i].name.replace(/'/g, '"'))
        factArray.push(fact)
    }
    deleteFactArray(factArray, source = 'aggs')
}

function ajaxDeleteFacts (form_data, factArray) {
    $.ajax({
        url: PREFIX + '/delete_facts',
        data: form_data,
        type: 'POST',
        contentType: false,
        processData: false,
        beforeSend: function () {
            swal({
                title: 'Starting fact remove job!',
                text: 'Removing facts from documents, this might take a while.',
                type: 'success'
            })
        },
        success: function () {
            for (var i = 0; i < factArray.length; i++) {
                removed_facts.push({
                    key: Object.keys(factArray[i])[0],
                    value: factArray[Object.keys(factArray[i])[0]]
                })
            }
            swal({
                title: 'Deleted!',
                text: factArray.length + ' facts have been removed.',
                type: 'success',
                showConfirmButton: false,
                timer: 1000
            })
        },
        error: function () {
            swal('Error!', 'There was a problem removing the facts!', 'error')
        }
    })
}

function deleteFactArray (factArray, source = 'aggs') {
    if (factArray.length >= 1) {
        var request = new XMLHttpRequest()
        var form_data = new FormData()
        for (var i = 0; i < factArray.length; i++) {
            for (var key in factArray[i]) {
                form_data.append(key, factArray[i][key])
            }
        }

        if (source == 'aggs') {
            swal({
                title: 'Are you sure you want to remove this fact from the dataset?',
                text: 'This will remove ' + factArray.length + ' facts from the dataset.',
                type: 'warning',
                showCancelButton: true,
                confirmButtonColor: '#73AD21',
                cancelButtonColor: '#d33',
                confirmButtonText: 'Yes, remove them!'
            }).then((result) => {
                if (result.value) {
                    ajaxDeleteFacts(form_data, factArray)
                }
            })
        } else if (source == 'fact_manager') {
            ajaxDeleteFacts(form_data, factArray)
        }
    } else {
        swal('Warning!', 'No facts selected!', 'warning')
    }
}

function addFactToSearch (fact_name, fact_val) {
    $('#constraint_field option').each(function () {
        if ($(this).val() != '') {
            if (JSON.parse($(this).val())['type'] == 'fact_str_val') {
                $('#constraint_field').val($(this).val())
                return false // break out of loop
            }
        }
    })

    var has_field = false
    $('span[id^=selected_field_]').each(function (index) {
        if ($(this).text().includes(['[fact_text_values]'])) {
            has_field = true
        }
    })
    if (!has_field) {
        addField('', '', '', false)
    }

    var split_id = $('input[name^=fact_txt_]').last().attr('id').split('_')
    var suggestion_id = split_id[split_id.length - 2] + '_' + split_id[split_id.length - 1]
    if (has_field) {
        addFactValueFieldConstraint(split_id[split_id.length - 2], $('#fact_field_' + split_id[split_id.length - 2]).val())
        var split_id = $('input[name^=fact_txt_]').last().attr('id').split('_')
        var suggestion_id = split_id[split_id.length - 2] + '_' + split_id[split_id.length - 1]
    }

    $('#field_' + split_id[split_id.length - 2] + ' #fact_txt_' + suggestion_id).val(fact_name)
    $('#fact_constraint_op_' + suggestion_id).val('=')
    $('#fact_constraint_val_' + suggestion_id).val(fact_val)
}

function show_string_children (data, children_container, grandchildren_container, row_key, type = null) {
    children_container.empty()
    grandchildren_container.empty()

    var tbody = $('<tbody></tbody>')
    $(data).each(function (fact_key) {
        var row_container = $('<tr><td>' + this.val + '</td><td>' + this.key + '</td></tr>')

        if (this.hasOwnProperty('children') && this.children.length > 0) {
            var row_container = $('<tr><td>' + this.val + '</td><td>' + this.key + "</td><td><span class='glyphicon glyphicon-menu-right'></span></td></tr>")
            row_container.addClass('pointer')
        } else {
            if (type == 'fact') {
                var fact_data = {}
                fact_data[fact_key] = this.key

                var add_to_search_icon = '<i class="glyphicon glyphicon-search pull-right"\
                data-toggle="tooltip" title="Add to search"\
                style="cursor: pointer"\
                onclick=\'addFactToSearch("' + fact_key + '","' + this.key + '");\'></i>'

                // keep track of checkboxes using their name as {NAME: VALUE}, otherwise when clicking on another fact name, they get overwritten
                checkboxName = JSON.stringify(fact_data).replace(/"/g, "'")
                var checkbox = '<input id="checkBox_' + this.val + '_' + this.key + '"\
                type="checkbox" name="' + checkboxName + '" onchange="factDeleteCheckbox(this)"'

                for (var i = 0; i < selectedFactCheckboxes.length; i++) {
                    if (selectedFactCheckboxes[i].name == checkboxName) {
                        checkbox = checkbox + ' checked'
                    }
                }

                var row_container = $('<tr><td>' + this.val + '</td><td>' + this.key + '</td><td>' + add_to_search_icon + '</td><td>' + checkbox + '></td></tr>')
            } else {
                var row_container = $('<tr><td>' + this.val + '</td><td>' + this.key + '</td><td></td></tr>')
            }
        };

        row_container.click(function () {
            grandchildren_container.empty()

            if (this.hasOwnProperty('children') && this.children.length > 0) {
                var grandchildrenTbody = $('<tbody></tbody>')

                $.each(this.children, function (j, grandchild_data) {
                    grandchildrenTbody.append($('<tr><td>' + grandchild_data.val + '</td><td>' + grandchild_data.key + '</td></tr>'))
                })

                var grandchildrenTable = $("<table class='table table-striped table-hover'></table>")
                grandchildrenTable.append("<thead><th colspan='2'>&nbsp;</th></head>")
                grandchildrenTable.append(grandchildrenTbody)

                grandchildren_container.append(grandchildrenTable)
                grandchildren_container.removeClass('hidden')
            }
        })

        tbody.append(row_container)
    }, [row_key])

    var table = $("<table class='table table-striped table-hover'></table>")

    var delete_checked_facts = '<i class="glyphicon glyphicon-trash pull-right"\
    data-toggle="tooltip" title="Delete checked facts"\
    style="cursor: pointer"\
    onclick=\'deleteFactsViaCheckboxes(selectedFactCheckboxes);\'></i>'

    table.append("<thead><th colspan='2'>Field #2</th><th colspan='1'></th><th colspan='1'>" + delete_checked_facts + '</th></head>') // .click(function(){children_container.addClass('hidden')});;
    table.append(tbody)

    children_container.append(table)
    children_container.removeClass('hidden')
}

function change_agg_field (field_nr) {
    var field_component = $('#agg_field_' + field_nr)
    var selected_field = field_component.val()
    var field_data = JSON.parse(selected_field)
    var selected_type = field_data['type']

    if (selected_type != 'date') {
        $('#sort_by_' + field_nr).removeClass('hidden')
        $('#agg_size_' + field_nr).removeClass('hidden')
        $('#freq_norm_' + field_nr).addClass('hidden')
        $('#interval_' + field_nr).addClass('hidden')
        $('#agg_daterange_' + field_nr).addClass('hidden')
    } else if (selected_type == 'date') {
        $('#agg_daterange_from_' + field_nr).val(field_data['range']['min'])
        $('#agg_daterange_to_' + field_nr).val(field_data['range']['max'])

        $('#agg_size_' + field_nr).addClass('hidden')
        $('#freq_norm_' + field_nr).removeClass('hidden')
        $('#interval_' + field_nr).removeClass('hidden')
        $('#sort_by_' + field_nr).addClass('hidden')
        $('#agg_daterange_' + field_nr).removeClass('hidden')
    }

    selected_method = $('#sort_by_' + field_nr).children('#sort_by_' + field_nr)
    selected_method.on('change', function () {
        // console.log(selected_method[0].options[selected_method[0].selectedIndex].text);
        if (selected_method[0].options[selected_method[0].selectedIndex].text == 'significant words') {
            $('#agg_field_2_button').addClass('hidden')
        } else {
            $('#agg_field_2_button').removeClass('hidden')
        }
    })
}

function toggle_agg_field_2 (action) {
    if (action == 'add') {
        $('#agg_field_2_container').removeClass('hidden')
        $('#agg_field_2_button').addClass('hidden')
        $('#agg_field_2_selected').val('true')
    } else {
        $('#agg_field_2_button').removeClass('hidden')
        $('#agg_field_2_container').addClass('hidden')
        $('#agg_field_2_selected').val('false')
    }
}

function loadUserPreference (dataset, mapping) {
    var hiddenFeatures = localStorage.getCacheItem('hiddenFeatures_' + dataset + '_' + mapping)
    if (hiddenFeatures) {
        for (var featureIdx in hiddenFeatures) {
            if (hiddenFeatures.hasOwnProperty(featureIdx)) {
                $('#feature-' + featureIdx).trigger('click')
            }
        }
    }
}

function cluster_to_lex (id) {
    var cluster_form = document.getElementById('save_as_lexicon_' + id)
    var fd = new FormData(cluster_form)
    fd.set('lexiconname', fd.get('lexiconname').split(' ').slice(0, -1).join(' '))
    $.ajax({
        url: LINK_LEXMINER + '/new',
        data: fd,
        type: 'POST',
        contentType: false,
        processData: false,
        success: function () {
            swal('Success!', 'Cluster saved as a lexicon!', 'success')
        },
        error: function () {
            swal('Error!', 'There was a problem saving the cluster as a lexicon!', 'error')
        }
    })
}
