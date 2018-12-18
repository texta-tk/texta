/* global swal PREFIX swalWarningDisplay */
var counter = 1
var factValSubCounter = {}
$(document).ready(function () {
    getSearches()
    changeAggField(1)
    $('#constraint_field').on('changed.bs.select', function (e, clickedIndex, isSelected, previousValue) {
        filterConstraintField($('#constraint_field option:selected').val())
    })

    var searchID = getUrlParameter('search')
    if (searchID !== undefined) {
        renderSavedSearch(searchID)
        /* global query */
        query()
    }
})

var getUrlParameter = function getUrlParameter (sParam) {
    let sPageURL = decodeURIComponent(window.location.search.substring(1))

    let sURLVariables = sPageURL.split('&')

    let sParameterName

    let i

    for (i = 0; i < sURLVariables.length; i++) {
        sParameterName = sURLVariables[i].split('=')

        if (sParameterName[0] === sParam) {
            return sParameterName[1] === undefined ? true : sParameterName[1]
        }
    }
}
function getQuery () {
    let formElement = document.getElementById('filters')
    let request = new XMLHttpRequest()

    request.onreadystatechange = function () {
        if (request.readyState === 4 && request.status === 200) {
            if (request.responseText.length > 0) {
                let queryQontainer = $('#query-modal-content')
                queryQontainer.html(JSON.stringify(JSON.parse(request.responseText)))
            }
        }
    }

    request.open('POST', PREFIX + '/get_query')
    request.send(new FormData(formElement), true)
}

function save () {
    const prompt = async () => {
        const {
            value: description
        } = await swal({
            title: 'Enter description for the search.',
            input: 'text',
            inputPlaceholder: 'description',
            showCancelButton: true,
            inputValidator: (value) => {
                return !value && 'Field empty!'
            }
        })
        if (description) {
            swal({
                type: 'success',
                title: 'Successfully saved search.'
            })

            $('#search_description').val(description)
            var formElement = document.getElementById('filters')
            var request = new XMLHttpRequest()
            request.onreadystatechange = function () {
                if (request.readyState === 4 && request.status === 200) {
                    getSearches()
                }
            }

            request.open('POST', PREFIX + '/save')
            request.send(new FormData(formElement), true)
        }
    }
    prompt()
}
function getSearches () {
    var request = new XMLHttpRequest()
    var formElement = document.getElementById('filters')

    request.onreadystatechange = function () {
        if (request.readyState === 4 && request.status === 200) {
            if (request.responseText.length > 0) {
                displaySearches(JSON.parse(request.responseText))
            }
        }
    }

    request.open('GET', PREFIX + '/listing')
    request.send(new FormData(formElement), true)
}

function removeSearchCallback (responseText) {
    var searchDiv = document.getElementById('search_' + responseText)
    searchDiv.parentNode.removeChild(searchDiv)
}

function removeSearches () {
    var searchesContainer = document.getElementById('saved_searches')
    let checkboxList = searchesContainer.getElementsByTagName('input')
    let pkArray = []
    for (let item of checkboxList) {
        if (item.checked) {
            pkArray.push(item.value)
        }
    }
    if (pkArray.length > 0) {
        deleteSelectedSearches(pkArray)
    } else {
        swalWarningDisplay('Please select a saved search first.')
    }
}
function deleteSelectedSearches (pkArray) {
    swal({
        title: 'Are you sure you want to delete this search?',
        text: 'The saved search will be deleted.',
        type: 'warning',
        showCancelButton: true,
        confirmButtonColor: '#73AD21',
        cancelButtonColor: '#d33',
        confirmButtonText: 'Yes'
    }).then((result) => {
        if (result.value) {
            $.ajax({
                url: PREFIX + '/delete',
                data: { data: JSON.stringify({ pks: pkArray }) },
                type: 'POST'
            }).then(() => {
                pkArray.forEach(element => {
                    let searchDiv = document.getElementById('search_' + element)
                    searchDiv.parentNode.removeChild(searchDiv)
                })
            })
        }
    })
}
function displaySearches (searches) {
    var searchesContainer = document.getElementById('saved_searches')
    while (searchesContainer.firstChild) {
        searchesContainer.removeChild(searchesContainer.firstChild)
    }

    for (var i = 0; i < searches.length; i++) {
        let searchDiv = document.createElement('tr')

        let inputElement = document.createElement('input')
        let urlElement = document.createElement('span')

        searchDiv.id = 'search_' + searches[i].id

        inputElement.type = 'checkbox'
        inputElement.name = 'saved_search_' + i
        inputElement.value = searches[i].id

        urlElement.className = 'glyphicon glyphicon-copy pointer'

        urlElement.onclick = (function (id) {
            return function () {
                var loc = window.location.href
                let searchUrl = loc + '?search=' + id

                const el = document.createElement('textarea')
                el.value = searchUrl
                document.body.appendChild(el)
                el.select()
                document.execCommand('copy')
                document.body.removeChild(el)

                const notification = swal.mixin({
                    toast: true,
                    position: 'bottom-start',
                    showConfirmButton: false,
                    timer: 3000
                })

                notification({
                    type: 'success',
                    title: 'Copied search link to clipboard',
                    text: searchUrl
                })
            }
        }(searches[i].id))

        let inputCol = document.createElement('td')
        inputCol.appendChild(inputElement)
        searchDiv.appendChild(inputCol)

        let textCol = document.createElement('td')
        let textNode = document.createTextNode(searches[i].desc)
        let renderAnchor = document.createElement('a')
        renderAnchor.appendChild(textNode)
        renderAnchor.title = 'Display search parameters'
        renderAnchor.setAttribute('role', 'button')
        renderAnchor.onclick = (function (id) {
            return function () {
                renderSavedSearch(id)
            }
        }(searches[i].id))

        textCol.appendChild(renderAnchor)
        searchDiv.appendChild(textCol)

        let urlCol = document.createElement('td')
        urlCol.appendChild(urlElement)
        searchDiv.appendChild(urlCol)

        searchesContainer.appendChild(searchDiv)
    }
}

function renderSavedSearch (searchID) {
    $.get(PREFIX + '/get_srch_query', {
        search_id: searchID
    }, function (data) {
        data = JSON.parse(data)

        $('#constraints').empty()
        for (var i = 0; i < data.length; i++) {
            renderSavedSearchField(data[i], '', '')
        }
    })
}

function renderSavedSearchField (fieldData, minDate, maxDate) {
    if (fieldData.constraint_type === 'date') {
        makeDateField(minDate, maxDate, fieldData)
        $(`#field_${counter.toString()} #daterange_from_${counter.toString()}`).val(fieldData.start_date)
        $(`#field_${counter.toString()} #daterange_to_${counter.toString()}`).val(fieldData.end_date)
    } else if (fieldData.constraint_type === 'string') {
        makeTextField(fieldData, true)
        $(`#match_operator_${counter.toString()}`).val(fieldData.operator)
        $(`#match_type_${counter.toString()}`).val(`match_${fieldData.match_type}`)
        $(`#match_slop_${counter.toString()}`).val(fieldData.slop)
        $(`#match_txt_${counter.toString()}`).val(fieldData.content.join('\n'))
    } else if (fieldData.constraint_type === 'facts') {
        makeFactField(fieldData)
        $(`#fact_operator_${counter.toString()}`).val(fieldData.operator)
        $(`#fact_txt_${counter.toString()}`).val(fieldData.content.join('\n'))
    } else if (fieldData.constraint_type === 'str_fact_val') {
        makeStrFactField(fieldData)
        $(`#fact_operator_${counter.toString()}`).val(fieldData.operator)
        for (var i = 0; i < fieldData.sub_constraints.length; i++) {
            var subConstraint = fieldData.sub_constraints[i]

            $('#fact_txt_' + counter.toString() + '_' + (factValSubCounter[counter.toString()] - 1)).val(subConstraint.fact_name)
            $('#fact_constraint_op_' + counter.toString() + '_' + (factValSubCounter[counter.toString()] - 1)).val(subConstraint.fact_val_operator)
            $('#fact_constraint_val_' + counter.toString() + '_' + (factValSubCounter[counter.toString()] - 1)).val(subConstraint.fact_val)

            if (i < fieldData.sub_constraints.length - 1) {
                addFactValueFieldConstraint(counter.toString(), fieldData.field)
            }
        }
    } else if (fieldData.constraint_type === 'num_fact_val') {

    }
}

function filterConstraintField (elementToFilter) {
    if (elementToFilter) {
        let fieldType = JSON.parse(elementToFilter).type
        $('#constraint_field option').each(function () {
            var val = $(this).val()
            var data = JSON.parse(val)
            if (data.type !== fieldType) {
                $(this).prop('disabled', true)
            }
        })
    } else {
        $('#constraint_field option').each(function () {
            $(this).prop('disabled', false)
        })
    }
    $('#constraint_field').selectpicker('refresh')
}

function makeDateField (dateRangeMin, dateRangeMax, fieldData) {
    counter++
    let newID = 'field_' + counter.toString()
    let fieldWithID = '#field_' + counter.toString()

    $('#field_hidden_date').clone().attr('id', newID).appendTo('#constraints')
    $(fieldWithID + ' #daterange_field_').attr('id', 'daterange_field_' + counter.toString()).attr('name', 'daterange_field_' + counter.toString()).val(fieldData.field)
    $(fieldWithID + ' #selected_field_').attr('id', 'selected_field_' + counter.toString()).attr('name', 'selected_field_' + counter.toString()).html(fieldData.field)
    $(fieldWithID + ' #remove_link').attr('onclick', "javascript:removeField('" + newID + "');")

    $(fieldWithID + ' #daterange_from_').attr('id', 'daterange_from_' + counter.toString())
    $(fieldWithID + ' #daterange_from_' + counter.toString()).attr('name', 'daterange_from_' + counter.toString())
    $(fieldWithID + ' #daterange_from_' + counter.toString()).datepicker({
        format: 'yyyy-mm-dd',
        startView: 2,
        startDate: dateRangeMin,
        endDate: dateRangeMax
    })
    $(fieldWithID + ' #daterange_to_').attr('id', 'daterange_to_' + counter.toString())
    $(fieldWithID + ' #daterange_to_' + counter.toString()).attr('name', 'daterange_to_' + counter.toString())
    $(fieldWithID + ' #daterange_to_' + counter.toString()).datepicker({
        format: 'yyyy-mm-dd',
        startView: 2,
        startDate: dateRangeMin,
        endDate: dateRangeMax
    })
    $(fieldWithID).show()
}

function makeFactField (fieldData) {
    counter++
    let newID = 'field_' + counter.toString()
    var fieldFullId = 'fact_txt_' + counter.toString()
    let fieldWithID = '#field_' + counter.toString()
    $('#field_hidden_fact').clone().attr('id', newID).appendTo('#constraints')
    $(fieldWithID + ' #fact_operator_').attr('id', 'fact_operator_' + counter.toString()).attr('name', 'fact_operator_' + counter.toString())
    $(fieldWithID + ' #selected_field_').attr('id', 'selected_field_' + counter.toString()).html(fieldData.field + ' [fact_names]')
    $(fieldWithID + ' #fact_field_').attr('id', 'fact_field_' + counter.toString()).attr('name', 'fact_field_' + counter.toString()).val(fieldData.field)
    $(fieldWithID + ' #remove_link').attr('onclick', "javascript:removeField('" + newID + "');")
    $(fieldWithID + ' #suggestions_').attr('id', 'suggestions_' + counter.toString()).attr('name', 'suggestions_' + counter.toString())
    $(fieldWithID + ' #fact_txt_').attr('id', 'fact_txt_' + counter.toString()).attr('name', 'fact_txt_' + counter.toString())
    $(fieldWithID + ' #fact_txt_' + counter.toString()).attr('onkeyup', 'lookup("' + fieldFullId + '",' + counter.toString() + ',"keyup", "FACT_NAME");')
    $(fieldWithID + ' #fact_txt_' + counter.toString()).attr('onfocus', 'lookup("' + fieldFullId + '","' + counter.toString() + '","focus", "FACT_NAME");')
    $(fieldWithID + ' #fact_txt_' + counter.toString()).attr('onblur', 'hide("' + counter.toString() + '");')
    $(fieldWithID).show()
}

function makeTextField (fieldData) {
    counter++
    let newID = 'field_' + counter.toString()
    var fieldFullId = 'fact_txt_' + counter.toString()
    let fieldWithID = '#field_' + counter.toString()
    $('#field_hidden').clone().attr('id', newID).appendTo('#constraints')
    $(fieldWithID + ' #match_operator_').attr('id', 'match_operator_' + counter.toString()).attr('name', 'match_operator_' + counter.toString())
    $(fieldWithID + ' #selected_field_').attr('id', 'selected_field_' + counter.toString()).html(fieldData.field)
    $(fieldWithID + ' #match_field_').attr('id', 'match_field_' + counter.toString()).attr('name', 'match_field_' + counter.toString()).val(fieldData.field)
    $(fieldWithID + ' #match_type_').attr('id', 'match_type_' + counter.toString()).attr('name', 'match_type_' + counter.toString())
    $(fieldWithID + ' #match_slop_').attr('id', 'match_slop_' + counter.toString()).attr('name', 'match_slop_' + counter.toString())
    $(fieldWithID + ' #remove_link').attr('onclick', "javascript:removeField('" + newID + "');")
    $(fieldWithID + ' #suggestions_').attr('id', 'suggestions_' + counter.toString()).attr('name', 'suggestions_' + counter.toString())
    $(fieldWithID + ' #match_txt_').attr('id', 'match_txt_' + counter.toString()).attr('name', 'match_txt_' + counter.toString())
    $(fieldWithID + ' #match_layer_').attr('id', 'match_layer_' + counter.toString()).attr('name', 'match_layer_' + counter.toString())

    var suggestionTypes = ['CONCEPT', 'LEXICON']
    fieldFullId = 'match_txt_' + counter.toString()

    $(fieldWithID + ' #match_txt_' + counter.toString()).attr('onkeyup', 'lookup("' + fieldFullId + '",' + counter.toString() + ',"keyup", \'' + suggestionTypes + '\'); searchAsYouTypeQuery();')
    $(fieldWithID + ' #match_txt_' + counter.toString()).attr('onfocus', 'lookup("' + fieldFullId + '","' + counter.toString() + '","focus", \'' + suggestionTypes + '\');')
    $(fieldWithID + ' #match_txt_' + counter.toString()).attr('onblur', 'hide("' + counter.toString() + '");')
    $(fieldWithID).show()
}

function makeStrFactField (fieldData) {
    var counterStr = counter.toString()
    var subCounter
    if (factValSubCounter[counterStr] === undefined) {
        subCounter = 1
    } else {
        subCounter = factValSubCounter[counterStr]
    }

    var subCounterStr = subCounter.toString()
    var idCombination = counterStr + '_' + subCounterStr

    if (fieldData.constraint_type === 'str_fact_val') {
        addFactValueField(counterStr, subCounterStr, fieldData.field, fieldData.field, 'str')
    } else if (fieldData.constraint_type === 'fact_num_val') {
        addFactValueField(counterStr, subCounterStr, fieldData.field, fieldData.field, 'num')
    }
    factValSubCounter[counterStr] = subCounter + 1
    $('#field_' + counter.toString()).show()
}

function addFactValueFieldConstraint (counterStr) {
    var subCounter
    if (factValSubCounter[counterStr] === undefined) {
        subCounter = 1
    } else {
        subCounter = factValSubCounter[counterStr]
    }

    var subCounterStr = subCounter.toString()

    var idCombination = counterStr + '_' + subCounterStr

    $('#fact_val_rule_').clone().attr('id', 'fact_val_rule_' + idCombination).appendTo('#fact_val_rules_' + counterStr)

    $('#field_' + counterStr + ' #fact_txt_').attr('id', 'fact_txt_' + idCombination).attr('name', 'fact_txt_' + idCombination)
    $('#field_' + counterStr + " input[name='fact_constraint_val_']").attr('name', 'fact_constraint_val_' + idCombination).attr('id', 'fact_constraint_val_' + idCombination)

    var keyFieldId = 'fact_txt_' + idCombination

    $('#field_' + counterStr + ' div[name=constraint_key_container] #suggestions_').attr('id', 'suggestions_' + idCombination).attr('name', 'suggestions_' + idCombination)
    $('#fact_txt_' + idCombination).attr('onkeyup', 'lookup("' + keyFieldId + '","' + idCombination + '","keyup", "FACT_NAME");')
    $('#fact_txt_' + idCombination).attr('onfocus', 'lookup("' + keyFieldId + '","' + idCombination + '","focus", "FACT_NAME");')
    $('#fact_txt_' + idCombination).attr('onblur', 'hide("' + idCombination + '");')

    var valIdCombination = idCombination + '_val'
    var valFieldId = 'fact_constraint_val_' + idCombination

    $('#field_' + counterStr + ' div[name=constraint_val_container] #suggestions_').attr('id', 'suggestions_' + valIdCombination).attr('name', 'suggestions_' + valIdCombination)
    $('#fact_constraint_val_' + idCombination).attr('onkeyup', 'lookup("' + valFieldId + '","' + valIdCombination + '","keyup", "FACT_VAL");')
    $('#fact_constraint_val_' + idCombination).attr('onfocus', 'lookup("' + valFieldId + '","' + valIdCombination + '","focus", "FACT_VAL");')
    $('#fact_constraint_val_' + idCombination).attr('onblur', 'hide("' + valIdCombination + '");')

    $('#fact_val_rule_' + idCombination + ' select').attr('name', 'fact_constraint_op_' + idCombination).attr('id', 'fact_constraint_op_' + idCombination)

    // Remove numeric operators from textual fact value
    if ($('#fact_constraint_type_' + counterStr).val() === 'str') {
        $('#fact_constraint_op_' + idCombination + ' option').filter(function (index) {
            return index in {
                2: null,
                3: null,
                4: null,
                5: null
            }
        }).remove()
    }

    var actionButtonContainer = $('#fact_val_rule_' + idCombination + " div[name='fact_action_button']")
    actionButtonContainer.empty()

    var removeButton = $('<button/>')
        .attr('type', 'button')
        .attr('onclick', 'removeFactRule("' + idCombination + '")')
        .addClass('btn btn-sm center-block')

    var removeSpan = $('<span/>')
        .addClass('glyphicon glyphicon-remove')
        .appendTo(removeButton)

    actionButtonContainer.append(removeButton)

    factValSubCounter[counterStr] = factValSubCounter[counterStr] + 1
}
function removeFactRule (ruleID) {
    $('#fact_val_rule_' + ruleID).remove()
}
function addFactValueField (counterStr, subCounterStr, fieldPath, fieldName, valueType) {
    var idCombination = counterStr + '_' + subCounterStr
    var headingSuffix
    if (valueType === 'str') {
        headingSuffix = ' [fact_text_values]'
    } else if (valueType === 'num') {
        headingSuffix = ' [fact_num_values]'
    }

    $('#field_hidden_fact_val').clone().attr('id', 'field_' + counterStr).appendTo('#constraints')
    $('#field_' + counterStr + ' #fact_operator_').attr('id', 'fact_operator_' + counterStr).attr('name', 'fact_operator_' + counterStr)
    $('#field_' + counterStr + ' #selected_field_').attr('id', 'selected_field_' + counterStr).html(fieldName + headingSuffix)
    $('#field_' + counterStr + ' #remove_link').attr('onclick', "javascript:removeField('field_" + counterStr + "');")
    $('#field_' + counterStr + ' #fact_field_').attr('id', 'fact_field_' + counterStr).attr('name', 'fact_field_' + counterStr).val(fieldPath)
    $('#field_' + counterStr + " input[name='fact_constraint_type_']")
        .attr('name', 'fact_constraint_type_' + counterStr)
        .attr('id', 'fact_constraint_type_' + counterStr)
        .val(valueType)

    $('#field_' + counterStr + ' #fact_txt_').attr('id', 'fact_txt_' + idCombination).attr('name', 'fact_txt_' + idCombination)
    $('#field_' + counterStr + " input[name='fact_constraint_val_']").attr('name', 'fact_constraint_val_' + idCombination).attr('id', 'fact_constraint_val_' + idCombination)

    $('#field_' + counterStr + ' #fact_val_rules_').attr('id', 'fact_val_rules_' + counterStr)
    $('#field_' + counterStr + ' #fact_val_rules_' + counterStr + ' #fact_val_rule_').attr('id', 'fact_val_rule_' + idCombination)
    $('#fact_val_rule_' + idCombination + ' select')
        .attr('name', 'fact_constraint_op_' + idCombination)
        .attr('id', 'fact_constraint_op_' + idCombination)

    // Remove numeric operators from textual fact value
    if ($('#fact_constraint_type_' + counterStr).val() === 'str') {
        $('#fact_constraint_op_' + idCombination + ' option').filter(function (index) {
            return index in {
                2: null,
                3: null,
                4: null,
                5: null
            }
        }).remove()
    }

    $('#field_' + counterStr + ' button').attr('onclick', 'addFactValueFieldConstraint("' + counterStr + '","' + fieldPath + '")')

    var keyFieldId = 'fact_txt_' + idCombination

    $('#field_' + counterStr + ' div[name=constraint_key_container] #suggestions_').attr('id', 'suggestions_' + idCombination).attr('name', 'suggestions_' + idCombination)
    $('#fact_txt_' + idCombination).attr('onkeyup', 'lookup("' + keyFieldId + '","' + idCombination + '","keyup", "FACT_NAME");')
    $('#fact_txt_' + idCombination).attr('onfocus', 'lookup("' + keyFieldId + '","' + idCombination + '","focus", "FACT_NAME");')
    $('#fact_txt_' + idCombination).attr('onblur', 'hide("' + idCombination + '");')

    var valIdCombination = idCombination + '_val'
    var valFieldId = 'fact_constraint_val_' + idCombination

    $('#field_' + counterStr + ' div[name=constraint_val_container] #suggestions_').attr('id', 'suggestions_' + valIdCombination).attr('name', 'suggestions_' + valIdCombination)
    $('#fact_constraint_val_' + idCombination).attr('onkeyup', 'lookup("' + valFieldId + '","' + valIdCombination + '","keyup", "FACT_VAL");')
    $('#fact_constraint_val_' + idCombination).attr('onfocus', 'lookup("' + valFieldId + '","' + valIdCombination + '","focus", "FACT_VAL");')
    $('#fact_constraint_val_' + idCombination).attr('onblur', 'hide("' + valIdCombination + '");')
}

function addField (dateRangeMin, dateRangeMax, submittedFieldData) {
    var field = []
    $('#constraint_field option').filter(':selected').each(function () {
        var val = $(this).val()
        field.push(val)
    })
    if (field.length <= 0) {
        swal('Warning!', 'No field selected!', 'warning')
        return
    }

    counter++

    var fieldPath = []
    var fieldData = []
    var fieldName = []

    field.forEach(function (data) {
        var jsonData = JSON.parse(data)
        fieldName.push(jsonData.label)
        fieldPath.push(jsonData.path)
    })

    fieldName = fieldName.join('; ')

    fieldData = JSON.parse(field[0])
    var fieldType = fieldData.type
    var nestedLayers = fieldData.nested_layers

    let newID = 'field_' + counter.toString()

    if (fieldType === 'date') {
        $('#field_hidden_date').clone().attr('id', newID).appendTo('#constraints')
        $('#field_' + counter.toString() + ' #daterange_field_').attr('id', 'daterange_field_' + counter.toString()).attr('name', 'daterange_field_' + counter.toString()).val(fieldPath)
        $('#field_' + counter.toString() + ' #selected_field_').attr('id', 'selected_field_' + counter.toString()).attr('name', 'selected_field_' + counter.toString()).html(fieldName)
        $('#field_' + counter.toString() + ' #remove_link').attr('onclick', "javascript:removeField('" + newID + "');")

        $('#field_' + counter.toString() + ' #daterange_from_').attr('id', 'daterange_from_' + counter.toString())
        $('#field_' + counter.toString() + ' #daterange_from_' + counter.toString()).attr('name', 'daterange_from_' + counter.toString())
        $('#field_' + counter.toString() + ' #daterange_from_' + counter.toString()).datepicker({
            format: 'yyyy-mm-dd',
            startView: 2,
            startDate: dateRangeMin,
            endDate: dateRangeMax
        })
        $('#field_' + counter.toString() + ' #daterange_to_').attr('id', 'daterange_to_' + counter.toString())
        $('#field_' + counter.toString() + ' #daterange_to_' + counter.toString()).attr('name', 'daterange_to_' + counter.toString())
        $('#field_' + counter.toString() + ' #daterange_to_' + counter.toString()).datepicker({
            format: 'yyyy-mm-dd',
            startView: 2,
            startDate: dateRangeMin,
            endDate: dateRangeMax
        })
    } else if (fieldType === 'facts') {
        var fieldFullID = 'fact_txt_' + counter.toString()

        $('#field_hidden_fact').clone().attr('id', newID).appendTo('#constraints')
        $('#field_' + counter.toString() + ' #fact_operator_').attr('id', 'fact_operator_' + counter.toString()).attr('name', 'fact_operator_' + counter.toString())
        $('#field_' + counter.toString() + ' #selected_field_').attr('id', 'selected_field_' + counter.toString()).html(fieldName + ' [fact_names]')
        $('#field_' + counter.toString() + ' #fact_field_').attr('id', 'fact_field_' + counter.toString()).attr('name', 'fact_field_' + counter.toString()).val(fieldPath)
        $('#field_' + counter.toString() + ' #remove_link').attr('onclick', "javascript:removeField('" + newID + "');")
        $('#field_' + counter.toString() + ' #suggestions_').attr('id', 'suggestions_' + counter.toString()).attr('name', 'suggestions_' + counter.toString())
        $('#field_' + counter.toString() + ' #fact_txt_').attr('id', 'fact_txt_' + counter.toString()).attr('name', 'fact_txt_' + counter.toString())
        $('#field_' + counter.toString() + ' #fact_txt_' + counter.toString()).attr('onkeyup', 'lookup("' + fieldFullID + '",' + counter.toString() + ',"keyup", "FACT_NAME");')
        $('#field_' + counter.toString() + ' #fact_txt_' + counter.toString()).attr('onfocus', 'lookup("' + fieldFullID + '","' + counter.toString() + '","focus", "FACT_NAME");')
        $('#field_' + counter.toString() + ' #fact_txt_' + counter.toString()).attr('onblur', 'hide("' + counter.toString() + '");')
    } else if (fieldType.substring(0, 5) === 'fact_') {
        var counterStr = counter.toString()
        var subCounter
        if (factValSubCounter[counterStr] === undefined) {
            subCounter = 1
        } else {
            subCounter = factValSubCounter[counterStr]
        }

        var subCounterStr = subCounter.toString()
        var idCombination = counterStr + '_' + subCounterStr

        if (fieldType === 'fact_str_val') {
            addFactValueField(counterStr, subCounterStr, fieldPath, fieldName, 'str')
        } else if (fieldType === 'fact_num_val') {
            addFactValueField(counterStr, subCounterStr, fieldPath, fieldName, 'num')
        }

        factValSubCounter[counterStr] = subCounter + 1
    } else {
        $('#field_hidden').clone().attr('id', newID).appendTo('#constraints')
        $('#field_' + counter.toString() + ' #match_operator_').attr('id', 'match_operator_' + counter.toString()).attr('name', 'match_operator_' + counter.toString())
        $('#field_' + counter.toString() + ' #selected_field_').attr('id', 'selected_field_' + counter.toString()).html(fieldName)
        $('#field_' + counter.toString() + ' #match_field_').attr('id', 'match_field_' + counter.toString()).attr('name', 'match_field_' + counter.toString()).val(fieldPath)
        $('#field_' + counter.toString() + ' #match_type_').attr('id', 'match_type_' + counter.toString()).attr('name', 'match_type_' + counter.toString())
        $('#field_' + counter.toString() + ' #match_slop_').attr('id', 'match_slop_' + counter.toString()).attr('name', 'match_slop_' + counter.toString())
        $('#field_' + counter.toString() + ' #remove_link').attr('onclick', "javascript:removeField('" + newID + "');")
        $('#field_' + counter.toString() + ' #suggestions_').attr('id', 'suggestions_' + counter.toString()).attr('name', 'suggestions_' + counter.toString())
        $('#field_' + counter.toString() + ' #match_txt_').attr('id', 'match_txt_' + counter.toString()).attr('name', 'match_txt_' + counter.toString())
        $('#field_' + counter.toString() + ' #match_layer_').attr('id', 'match_layer_' + counter.toString()).attr('name', 'match_layer_' + counter.toString())

        var suggestionTypes = ['CONCEPT', 'LEXICON']
        fieldFullID = 'match_txt_' + counter.toString()

        $('#field_' + counter.toString() + ' #match_txt_' + counter.toString()).attr('onkeyup', 'lookup("' + fieldFullID + '",' + counter.toString() + ',"keyup", \'' + suggestionTypes + '\'); searchAsYouTypeQuery();')
        $('#field_' + counter.toString() + ' #match_txt_' + counter.toString()).attr('onfocus', 'lookup("' + fieldFullID + '","' + counter.toString() + '","focus", \'' + suggestionTypes + '\');')
        $('#field_' + counter.toString() + ' #match_txt_' + counter.toString()).attr('onblur', 'hide("' + counter.toString() + '");')

        if (nestedLayers.length > 0) {
            $.each(nestedLayers, function (index, value) {
                $('#field_' + counter.toString() + ' #match_layer_' + counter.toString()).append(new Option('Match layer: ' + value, value))
            })
        }
    }

    $('#field_' + counter.toString()).show()
}

function searchAsYouTypeQuery () {
    var selection = $('#search_as_you_type').prop('checked')
    var keyTimer
    if (selection) {
        clearTimeout(keyTimer)
        keyTimer = setTimeout(function validate () {
            query()
        }, 500)
    }
}

function hideShowOptions () {
    var x = document.getElementById('short_version_options')

    if (x.style.display === 'none') {
        x.style.display = 'block'
    } else {
        x.style.display = 'none'
    }
}

function hideShowOptionsCluster () {
    var x = document.getElementById('short_version_options_cluster')

    if (x.style.display === 'none') {
        x.style.display = 'block'
    } else {
        x.style.display = 'none'
    }
}

function clusterQuery () {
    var formElement = document.getElementById('filters')
    var request = new XMLHttpRequest()

    request.onreadystatechange = function () {
        $('#right').html(`loading ${request.readyState}/4'`)
        if (request.readyState === 4) {
            $('#right').html('')
            if (request.status === 200) {
                $('#right').html(request.responseText)
            }
            if (request.status === 400 && request.statusText === 'field') {
                swalWarningDisplay('Please select a field first')
            }
        }
    }

    request.open('POST', PREFIX + '/cluster_query')
    request.send(new FormData(formElement))
}

function lookup (fieldFullId, fieldId, action, lookupTypes) {
    var content = $('#' + fieldFullId).val()
    let factName
    if (fieldFullId.match('^fact_constraint_val_')) {
        factName = $('#fact_txt_' + fieldId.slice(0, -4)).val()
    } else {
        factName = ''
    }

    var lookupData = {
        content: content,
        action: action,
        lookup_types: lookupTypes,
        key_constraints: factName
    }
    $.post(PREFIX + '/autocomplete', lookupData, function (data) {
        if (data.length > 0) {
            var suggestionsContainer = $('#suggestions_' + fieldId)
            suggestionsContainer.empty()

            processSuggestions(data, suggestionsContainer, fieldId, lookupTypes)
            if (suggestionsContainer.html()) {
                $('#suggestions_' + fieldId).show()
            }
        } else {
            $('#suggestions_' + fieldId).hide()
        }
    })
}

function processSuggestions (suggestions, suggestionsContainer, fieldID, lookupTypes) {
    suggestions = JSON.parse(suggestions)

    $.each(suggestions, function (lookupType, lookupSuggestions) {
        if (lookupSuggestions.length > 0) {
            var li = $('<div/>')
                .text(lookupType)
                .css('font-weight', 'Bold')
                .appendTo(suggestionsContainer)

            $.each(lookupSuggestions, function (i) {
                var li = $('<li/>')
                    .addClass('list-group-item')
                    .addClass('pointer')
                    .attr('onclick', "insert('" + lookupSuggestions[i]['resource_id'] + "','" + fieldID + "','" + lookupSuggestions[i]['entry_text'] + "','" + lookupType + "')")
                    .html(lookupSuggestions[i]['display_text'])
                    .appendTo(suggestionsContainer)
            })
        }
    })
}

function insert (resourceID, suggestionID, descriptiveTerm, lookupType) {
    if (resourceID) {
        let suggestionPrefix
        if (lookupType === 'CONCEPT') {
            suggestionPrefix = '@C'
        } else if (lookupType === 'LEXICON') {
            suggestionPrefix = '@L'
        }

        $('#field_' + suggestionID + ' #match_txt_' + suggestionID).val(function (index, value) {
            return value.replace(/[^(\n)]*$/, '')
        })
        $('#field_' + suggestionID + ' #match_txt_' + suggestionID).val($('#field_' + suggestionID + ' #match_txt_' + suggestionID).val() + suggestionPrefix + resourceID + '-' + descriptiveTerm + '\n')
        $('#field_' + suggestionID + ' #match_txt_' + suggestionID).focus()
    } else {
        if (lookupType === 'TEXT') {
            $('#field_' + suggestionID + ' #match_txt_' + suggestionID).val(function (index, value) {
                return value.replace(/[^(\n)]*$/, '')
            })
            $('#field_' + suggestionID + ' #match_txt_' + suggestionID).val($('#field_' + suggestionID + ' #match_txt_' + suggestionID).val() + descriptiveTerm + '\n')
        }
        if (lookupType === 'FACT_NAME') {
            var separatorIdx = suggestionID.indexOf('_')
            let fieldID
            if (separatorIdx > -1) {
                fieldID = suggestionID.substring(0, separatorIdx)
            } else {
                fieldID = suggestionID
            }

            if (separatorIdx > -1) {
                $('#field_' + fieldID + ' #fact_txt_' + suggestionID).val(descriptiveTerm)
            } else {
                $('#field_' + fieldID + ' #fact_txt_' + suggestionID).val(function (index, value) {
                    return value.replace(/[^(\n)]*$/, '')
                })
                $('#field_' + fieldID + ' #fact_txt_' + suggestionID).val($('#field_' + suggestionID + ' #fact_txt_' + suggestionID).val() + descriptiveTerm + '\n')
            }
        }
        if (lookupType === 'FACT_VAL') {
            var suggestionIdPrefix = suggestionID.replace('_val', '')
            $('#fact_constraint_val_' + suggestionIdPrefix).val(descriptiveTerm)
        }
    }
}

function mltQuery () {
    var formElement = document.getElementById('filters')
    var mltField = $("select[id='mlt_fields']").val()
    var request = new XMLHttpRequest()

    if (mltField != null) {
        request.onreadystatechange = function () {
            $('#right').html(`loading ${request.readyState}/4'`)
            if (request.readyState === 4) {
                $('#right').html('')
                if (request.status === 200) {
                    $('#right').html(request.responseText)
                }
                if (request.status === 400 && request.statusText === 'field') {
                    swalWarningDisplay('Please select a field first')
                }
            }
        }
        request.open('POST', PREFIX + '/mlt_query')
        request.send(new FormData(formElement))
    } else {
        $('#right').html('No fields selected!')
    }
}

function removeField (id) {
    $('#' + id).remove()
}

function togglePanelCollapse (element) {
    $(element).toggleClass('glyphicon-plus')
    $(element).toggleClass('glyphicon-minus')
}

function changeAggField (fieldNumber) {
    var fieldComponent = $('#agg_field_' + fieldNumber)
    var selectedField = fieldComponent.val()
    var fieldData = JSON.parse(selectedField)
    var selectedType = fieldData['type']

    if (selectedType !== 'date') {
        $('#sort_by_' + fieldNumber).removeClass('hidden')
        $('#agg_size_' + fieldNumber).removeClass('hidden')
        $('#freq_norm_' + fieldNumber).addClass('hidden')
        $('#interval_' + fieldNumber).addClass('hidden')
        $('#agg_daterange_' + fieldNumber).addClass('hidden')
    } else if (selectedType === 'date') {
        $('#agg_daterange_from_' + fieldNumber).val(fieldData['range']['min'])
        $('#agg_daterange_to_' + fieldNumber).val(fieldData['range']['max'])

        $('#agg_size_' + fieldNumber).addClass('hidden')
        $('#freq_norm_' + fieldNumber).removeClass('hidden')
        $('#interval_' + fieldNumber).removeClass('hidden')
        $('#sort_by_' + fieldNumber).addClass('hidden')
        $('#agg_daterange_' + fieldNumber).removeClass('hidden')
    }

    let selectedMethod = $('#sort_by_' + fieldNumber).children('#sort_by_' + fieldNumber)
    selectedMethod.on('change', function () {
        // console.log(selected_method[0].options[selected_method[0].selectedIndex].text);
        if (selectedMethod[0].options[selectedMethod[0].selectedIndex].text === 'significant words') {
            $('#agg_field_2_button').addClass('hidden')
        } else {
            $('#agg_field_2_button').removeClass('hidden')
        }
    })
}

function toggleAggField2 (action) {
    if (action === 'add') {
        $('#agg_field_2_container').removeClass('hidden')
        $('#agg_field_2_button').addClass('hidden')
        $('#agg_field_2_selected').val('true')
    } else {
        $('#agg_field_2_button').removeClass('hidden')
        $('#agg_field_2_container').addClass('hidden')
        $('#agg_field_2_selected').val('false')
    }
}
