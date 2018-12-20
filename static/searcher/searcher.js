/* eslint-disable no-multi-str */
/* global LINK_SEARCHER */
var PREFIX = LINK_SEARCHER
var examplesTable


$(document).ready(function () {
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

    $(window).resize(function (e, settings) {
        recalcDatatablesHeight()
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
    $('#constraint_field').on('loaded.bs.select', function (e, clickedIndex, isSelected, previousValue) {
        let button = $('#constraint-field-button')
        button.appendTo('.constraint-field-wrapper > div > div > div.bs-actionsbox')
        button.removeClass('hidden')
    })
})

function hide (id) {
    var separatorIdx = id.indexOf('_')
    let fieldID
    if (separatorIdx > -1) {
        fieldID = id.substring(0, separatorIdx)
    } else {
        fieldID = id
    }
    $('#field_' + fieldID + ' #suggestions_' + id).mouseleave(function () {
        if (!$('#field_' + fieldID + ' #suggestions_' + id).is(':hover')) {
            $('#field_' + fieldID + ' #suggestions_' + id).hide()
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
function query () {
    var formElement = document.getElementById('filters')
    var request = new XMLHttpRequest()
    request.onreadystatechange = function () {
        if (request.readyState === 4 && request.status === 200) {
            $('#right').html(request.responseText)
            // Get header column names
            // Used for setting title to all elements in corresponding column
            // Which can be used as column selectors/for retriving column name
            var columns = []
            $('#columnsRow').find('th').each(function (index) {
                // Append _DtCol to end to safe from naming conflicts
                columns.push({ 'className': 'DtCol_' + $(this).text(), 'targets': index })
            })
            examplesTable = $('#examples').DataTable({
                'autoWidth': false,
                'deferRender': true,
                'scrollY': '100vh',
                'bServerSide': true,
                'processing': true,
                'filter': false,
                'sAjaxSource': PREFIX + '/table_content',
                'dom': '<"#top-part.flex-row"<"flex-item-grow-1 flex-row align-center"<"flex-item-grow-1 flex-row align-center toggle-columns-select height-max"<"fullscreen-actions-div">>><"flex-content-end flex-item-grow-3 align-center"<"flex-item-grow-2"i><"flex-item-grow-1"l><"flex-item-grow-2"p>>>t',
                'sServerMethod': 'POST',
                'fnServerParams': function (aoData) {
                    aoData.push({
                        'name': 'filterParams',
                        'value': JSON.stringify($('#filters').serializeArray())
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
                    // Initialize clicking HLs/selection text for properties
                    /* global createSelectionProps, selectionProps */
                    createSelectionProps()
                    recalcDatatablesHeight()
                },
                'stateSave': true,
                'stateSaveParams': function (settings, data) {
                    data.start = 0
                },
                'stateLoadParams': function (settings, data) {
                    /*  because state has the last saved state of the table, not the current one then we can check
                    if the selected datasets were changed and if extra columns were added, removed,
                    if they were then select all (also did this in previous version, with buttons) */
                    if ($('#examples').DataTable().columns().nodes().length !== data.columns.length) {
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
                'scrollX': true,
                // Add title with the corresponding column name to each element in column
                'columnDefs': columns,
                'ordering': false
            })
            $.fn.DataTable.ext.pager.numbers_length = 5
            initColumnSelectVisiblity(examplesTable)
            var dataset = $('#dataset').val()
            var mapping = $('#mapping').val()
            var div = $('.toggle-columns-select')
            var button = $('.toggle-column-select-wrapper')
            button.appendTo(div)

            if ($('.fullscreen-actions-div > i').length === 0) {
                $('.glyphicon-fullscreen-content-searcher').clone().addClass('new-toggle').appendTo($('.fullscreen-actions-div'))
            }
            loadUserPreference(dataset, mapping)
            $('#actions-btn').removeClass('invisible')
            $('#export-examples-modal').removeClass('invisible')
            $('#export-aggregation-modal').addClass('invisible')
        }
    }

    request.open('POST', PREFIX + '/table_header')
    request.send(new FormData(formElement))
}
function recalcDatatablesHeight () {
    if (examplesTable) {
        let datatablesNavHeight = $('#top-part').height()
        let navbarHeight = $('.grid-item-navbar').height()
        let datatablesColumHeight = $('div.dataTables_scrollHead').height()
        let datatablesScrollBody = $(window).height()
        $('div.dataTables_scrollBody').height(datatablesScrollBody - datatablesColumHeight - navbarHeight - datatablesNavHeight - 20)
    }
}
function initColumnSelectVisiblity (examplesTable) {
    var $select = $('#toggle-column-select')
    $select.selectpicker({
        style: 'btn btn-default'
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
function acceptDocument (id) {
    $('#docs').val($('#docs').val() + id + '\n')
    $('#row_' + id).remove()
}

function rejectDocument (id) {
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
        if (request.readyState === 4 && request.status === 200) {
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
        if (request.readyState === 4 && request.status === 200) {
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

    var stringContainer = $("<div id='string_agg_container'></div>")
    var chartContainer = $("<div id='daterange_agg_container'></div>")

    container.append(chartContainer)
    container.append(stringContainer)

    for (var i in data) {
        if (data.hasOwnProperty(i)) {
            if (data[i].type === 'daterange') {
                drawTimeline(data[i])
            } else if (data[i].type === 'string') {
                drawStringAggs(data[i])
            } else if (data[i].type === 'fact') {
                drawStringAggs(data[i], 'fact')
            } else if (data[i].type === 'fact_str_val') {
                drawStringAggs(data[i])
            } else if (data[i].type === 'fact_num_val') {
                drawStringAggs(data[i])
            }
        }
    }
}

function drawTimeline (data) {
    var timelineChildrenContainer = $('<div></div>')
    /* global Morris  */
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
        var childrenData = data.children[row.date]
        showChildren(childrenData, row.date, timelineChildrenContainer)
    })

    $('#right').append(timelineChildrenContainer)
}

function showChildren (data, date, timelineChildrenContainer) {
    timelineChildrenContainer.empty()
    $.each(data, function (i, dataList) {
        var responseContainers = [$("<div style='float: left; padding-left: 20px;'></div>")]

        var tbody = $('<tbody></tbody>')

        var valTables = []

        $.each(dataList.data, function (j, row) {
            var rowContainer = $('<tr><td>' + row.val + '</td><td>' + row.key + '</td></tr>')

            var valsTbody = $('<tbody></tbody>')
            var valsTable = $("<table id='" + i + '-' + row.key + "-table' class='table table-striped table-hover fact-val-table-" + i + "' style='display: none;'></table>")
            valsTable.append("<thead><th colspan='2'>&nbsp;</th></head>")

            if (!row.hasOwnProperty('children')) {
                row.children = []
            }

            $.each(row.children, function (k, childRow) {
                valsTbody.append($('<tr><td>' + childRow.val + '</td><td>' + childRow.key + '</td></tr>'))
            })

            rowContainer.click(function () {
                $('.fact-val-table-' + i).hide()
                $('#' + i + '-' + row.key + '-table').show()
            })

            valsTable.append(valsTbody)

            if (row.children.length > 0) {
                rowContainer.addClass('pointer')

                var responseContainer = $("<div style='float: left; padding-left: 20px;'></div>")
                responseContainer.append(valsTable)
                responseContainers.push(responseContainer)
            }

            tbody.append(rowContainer)
        })

        var table = $("<table class='table table-striped table-hover'></table>")
        table.append("<thead><th colspan='2'>" + dataList.label + '</th></head>')
        table.append(tbody)
        responseContainers[0].append(table)

        $.each(responseContainers, function (i, container) {
            timelineChildrenContainer.append(container)
        })
    })
}

function drawStringAggs (data, type = null) {
    var responseContainer = $("<div style='float: left; padding-left: 20px;'></div>")
    var tableContainer = $("<div style='float: left'></div>")
    var childrenContainer = $("<div style='background-color: white; float: left; min-width: 200px;' class='hidden'></div>")
    var grandchildrenContainer = $("<div id='grandchildren_container' style='background-color: white; float: left; min-width: 200px;' class='hidden'></div>")

    var tbody = $('<tbody></tbody>')

    $.each(data.data, function (i, row) {
        let rowContainer
        if (row.children.length > 0) {
            rowContainer = $('<tr><td>' + row.val + '</td><td>' + row.key + "</td><td><span class='glyphicon glyphicon-menu-right'></span></td></tr>")
            rowContainer.click(function () {
                showStringChildren(row.children, childrenContainer, grandchildrenContainer, row.key, type)
            })
            rowContainer.addClass('pointer')
        } else {
            rowContainer = $('<tr><td>' + row.val + '</td><td>' + row.key + '</td><td></td></tr>')
        }
        tbody.append(rowContainer)
    })

    var table = $("<table class='table table-striped table-hover'></table>")
    table.append("<thead><th colspan='2'>Field #1</th></head>")
    table.append(tbody)

    tableContainer.append(table)

    responseContainer.append("<div class='row text-center'><h3>" + data.label + '</h3></div>')
    responseContainer.append(tableContainer)
    responseContainer.append(childrenContainer)
    responseContainer.append(grandchildrenContainer)

    $('#string_agg_container').append(responseContainer)
}

var selectedFactCheckboxes = []

function factDeleteCheckbox (checkbox) {
    let inArray = false
    if (!selectedFactCheckboxes.length > 0) {
        selectedFactCheckboxes.push(checkbox)
    } else {
        let i = 0
        while (!inArray && i < selectedFactCheckboxes.length) {
            if (selectedFactCheckboxes[i].name === checkbox.name) {
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
    let factArray = []
    for (var i = 0; i < checkboxes.length; i++) {
        let fact = JSON.parse(checkboxes[i].name.replace(/'/g, '"'))
        factArray.push(fact)
    }
    deleteFactArray(factArray, 'aggs')
}

function ajaxDeleteFacts (formData, factArray) {
    $.ajax({
        url: PREFIX + '/delete_facts',
        data: formData,
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

function deleteFactArray (factArray, source) {
    if (factArray.length >= 1) {
        var formData = new FormData()
        for (var i = 0; i < factArray.length; i++) {
            for (var key in factArray[i]) {
                formData.append(key, factArray[i][key])
            }
        }

        if (source === 'aggs') {
            /* global swal */
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
                    ajaxDeleteFacts(formData, factArray)
                }
            })
        } else if (source === 'fact_manager') {
            ajaxDeleteFacts(formData, factArray)
        }
    } else {
        swal('Warning!', 'No facts selected!', 'warning')
    }
}

function showStringChildren (data, childrenContainer, grandchildrenContainer, rowKey, type) {
    childrenContainer.empty()
    grandchildrenContainer.empty()

    var tbody = $('<tbody></tbody>')
    $(data).each(function (index) {
        var rowContainer = $('<tr><td>' + this.val + '</td><td>' + this.key + '</td></tr>')

        if (this.hasOwnProperty('children') && this.children.length > 0) {
            rowContainer = $('<tr><td>' + this.val + '</td><td>' + this.key + "</td><td><span class='glyphicon glyphicon-menu-right'></span></td></tr>")
            rowContainer.addClass('pointer')
        } else {
            if (type === 'fact') {
                var factData = {}
                factData[rowKey] = this.key
<<<<<<< HEAD
                var addToSearchIcon = `<i class="glyphicon glyphicon-search pull-right"\
                data-toggle="tooltip" title="Add to search"\
                style="cursor: pointer"\
                onclick=\'addFactToSearch("${rowKey}","${this.key}");\'></i>`
                addToSearchIcon = strip(addToSearchIcon)
=======

                searchKey = strip_html(rowKey, true)
                searchVal = strip_html(this.key, true)
                var addToSearchIcon = `<i class="glyphicon glyphicon-search pull-right" data-toggle="tooltip" title="Add to search"\
                style="cursor: pointer" onclick="addFactToSearch('${searchKey}','${searchVal}');"></i>`
>>>>>>> entity_extractor

                // keep track of checkboxes using their name as {NAME: VALUE}, otherwise when clicking on another fact name, they get overwritten
                let checkboxName = JSON.stringify(factData).replace(/"/g, "'")
                var checkbox = `<input id="checkBox_${rowKey}_${this.key}"\
                type="checkbox" name="${checkboxName}" onchange="factDeleteCheckbox(this)"`

                for (var i = 0; i < selectedFactCheckboxes.length; i++) {
                    if (selectedFactCheckboxes[i].name === checkboxName) {
                        checkbox = checkbox + ' checked'
                    }
                }

                rowContainer = $(`<tr><td> ${this.val} </td><td> ${this.key} </td><td> ${addToSearchIcon}</td><td> ${checkbox}></td></tr>`)
            } else {
                rowContainer = $(`<tr><td> ${this.val} </td><td> ${this.key} </td><td></td></tr>`)
            }
        };

        rowContainer.click(function () {
            grandchildrenContainer.empty()

            if (this.hasOwnProperty('children') && this.children.length > 0) {
                var grandchildrenTbody = $('<tbody></tbody>')

                $.each(this.children, function (j, grandchildData) {
                    grandchildrenTbody.append($('<tr><td>' + grandchildData.val + '</td><td>' + grandchildData.key + '</td></tr>'))
                })

                var grandchildrenTable = $("<table class='table table-striped table-hover'></table>")
                grandchildrenTable.append("<thead><th colspan='2'>&nbsp;</th></head>")
                grandchildrenTable.append(grandchildrenTbody)

                grandchildrenContainer.append(grandchildrenTable)
                grandchildrenContainer.removeClass('hidden')
            }
        })

        tbody.append(rowContainer)
    }, [rowKey])

    var table = $("<table class='table table-striped table-hover'></table>")

    var deleteCheckedFacts = '<i class="glyphicon glyphicon-trash pull-right"\
    data-toggle="tooltip" title="Delete checked facts"\
    style="cursor: pointer"\
    onclick=\'deleteFactsViaCheckboxes(selectedFactCheckboxes);\'></i>'

    table.append("<thead><th colspan='2'>Field #2</th><th colspan='1'></th><th colspan='1'>" + deleteCheckedFacts + '</th></head>') // .click(function(){children_container.addClass('hidden')});;
    table.append(tbody)

    childrenContainer.append(table)
    childrenContainer.removeClass('hidden')
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

function clusterToLex (id) {
    var clusterForm = document.getElementById('save_as_lexicon_' + id)
    var fd = new FormData(clusterForm)
    fd.set('lexiconname', fd.get('lexiconname').split(' ').slice(0, -1).join(' '))
    /* global LINK_LEXMINER */
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

function addFactToSearch (factName, factVal) {
    $('#constraint_field option').each(function () {
        if ($(this).val() !== '') {
            if (JSON.parse($(this).val())['type'] === 'fact_str_val') {
                $('#constraint_field').val($(this).val())
                return false // break out of loop
            }
        }
    })

    var hasField = false
    $('span[id^=selected_field_]').each(function (index) {
        if ($(this).text().includes(['[fact_text_values]'])) {
            hasField = true
        }
    })
    if (!hasField) {
        /* global addField, sidebar */
        addField('', '', false)
    }

    var splitID = $('input[name^=fact_txt_]').last().attr('id').split('_')
    var suggestionID = splitID[splitID.length - 2] + '_' + splitID[splitID.length - 1]
    if (hasField) {
        /* global addFactValueFieldConstraint, searcher-sidebar */
        addFactValueFieldConstraint(splitID[splitID.length - 2], $('#fact_field_' + splitID[splitID.length - 2]).val())
        splitID = $('input[name^=fact_txt_]').last().attr('id').split('_')
        suggestionID = splitID[splitID.length - 2] + '_' + splitID[splitID.length - 1]
    }

    $('#field_' + splitID[splitID.length - 2] + ' #fact_txt_' + suggestionID).val(factName)
    $('#fact_constraint_op_' + suggestionID).val('=')
    $('#fact_constraint_val_' + suggestionID).val(factVal)
}

function deleteFactFromDoc (fact_name, fact_value, doc_id) {
    var request = new XMLHttpRequest()
    var form_data = new FormData()
    form_data.append(fact_name, fact_value)
    form_data.append('doc_id', doc_id)

    swal({
        title: 'Are you sure you want to remove this fact from the dataset?',
        text: `This will remove ${fact_name}: ${fact_value} from document ${doc_id}.`,
        type: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#73AD21',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Yes, remove!'
    }).then((result) => {
        if (result.value) {
            ajaxDeleteFacts(form_data, [{ [fact_name]: fact_value }])
        }
    })
}

function strip_html(html, removeNewlines){
    // Strip html from string, optionally remove newlines
    var doc = new DOMParser().parseFromString(html, 'text/html');
    newContent = doc.body.textContent

    if (removeNewlines) {
        newContent = newContent.replace(/(\r\n\t|\n|\r\t)/gm," ");
    }

    return newContent || "";
}
