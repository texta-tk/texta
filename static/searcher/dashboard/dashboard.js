var PREFIX = LINK_SEARCHER;
var ColorSettings = Object.freeze({"GLOBAL": 'color-global', "FIELD": 'color-field'})
var Colors = Object.freeze({"COLOR_MIN": colorMinimum, "COLOR_MAX": colorMaximum})
$(function () {

    updateLoaderStatus('Getting data from the server')
    $.ajax({
        type: "get",
        url: PREFIX + '/dashboard',
        error: function (request, error) {
            swalCustomTypeDisplay(SwalType.ERROR, request.statusText)
            $('#right').empty()
        },
        success: function (data) {
            if (checkNested(data, 'indices')) {
                updateLoaderStatus('Drawing Dashboard')
                let indicesArray = [];
                createIndices(indicesArray, data)
                initListeners();
                initDashBoard(indicesArray);
                //no point showing upper navtab when you only have 1 index
                if(indicesArray.length===1){
                    $('#outermost-navtab').remove()
                }
                removeLoader()
            }
        }
    });
});

function updateLoaderStatus(x) {
    $('#loader-text').text(x)
}

function removeLoader() {
    $('.loader-wrapper').addClass('hidden')
    $('#outermost-wrapper-dashboard').removeClass('hidden')
}

function createIndices(indicesArray, data) {
    data.indices.forEach((element) => {
        indicesArray.push(new Index(element.aggregations, element.index_name, element.total_documents))
    });
    return indicesArray
}

function initListeners() {
    let previous = '';
    $('#index_fields').on('change', function () {
        if (previous === '') {
            $(`#datatables-container-${this.value}`).removeClass('hidden');
            previous = this.value
        } else {
            $(`#datatables-container-${previous}`).addClass('hidden');
            $(`#datatables-container-${this.value}`).removeClass('hidden');
            previous = this.value
        }
    });
}

function initDashBoard(indices) {
    indices.forEach((e) => {
        makeFrequentItemsTables(e);
        makeSignificantWordsTables(e);
        makeFactsTables(e);
        makeStatistics(e);
        makeTimelines(e);
    })
}

function makeTimelines(index) {
    let width = getHiddenDivMaxWidth(`timeline-agg-container-month-${index.index_name}`)
    /*more readable and scalable like this, really dont want to make this into 1 function*/
    makeMonthTimeline(index, width)
    makeYearTimeline(index, width)
}

function makeMonthTimeline(index, width) {
    let dates = index.getDatesMonth();

    let div = document.getElementById(`timeline-agg-container-month-${index.index_name}`);
    if (dates) {
        let xData = dates.map((e) => e.key_as_string);
        let yData = dates.map((e) => e.doc_count);
        const layout = {

            title: `By month`,
            width: width
        }
        Plotly.newPlot(div, [{
            x: xData,
            y: yData
        }], layout);

    } else {
        div.remove()
    }

}

function makeYearTimeline(index, width) {
    let dates = index.getDatesYear();

    let div = document.getElementById(`timeline-agg-container-year-${index.index_name}`);
    if (dates) {
        let xData = dates.map((e) => e.key_as_string);
        let yData = dates.map((e) => e.doc_count);
        const layout = {

            title: `By year`,
            width: width
        }
        Plotly.newPlot(div, [{
            x: xData,
            y: yData
        }], layout);

    } else {
        div.remove()
    }


}

function makeFactsTables(index) {
    let result = formatFacts(index)
    /*has to be a number field*/
    let colorRowIndex = 1
    if (result) {
        let t_id = 0;
        /*nested*/
        result.forEach((e) => {
            let resultFormatted = e.facts.map((x) => {
                return [x.key, x.doc_count]
            });
            if (resultFormatted.length > 1) {

                let minMax = getColorRange(resultFormatted, colorRowIndex, index)
                let color = d3.scale.linear()
                    .domain([minMax[0], minMax[1]])
                    .range([d3.rgb(Colors.COLOR_MIN), d3.rgb(Colors.COLOR_MAX)]);

                let tableID = `${index.AggregationTpes.NESTED}-generated-${index.index_name}${t_id}`
                $(`#${index.index_name}-nested-table`).append(`<table id="${tableID}" style="width:100%"><caption class="dashboard-caption">${e.key}</caption></table>`);

                $(`#${tableID}`).DataTable({
                    data: resultFormatted,
                    dom: 't',
                    ordering: true,
                    order: [1, 'desc'],
                    paging: false,
                    columns: [
                        {title: "facts"},
                        {title: "count"}
                    ],
                    "rowCallback": function (row, data, index) {
                        $($(row).children()[colorRowIndex]).css('background-color', color(data[colorRowIndex]))
                    }
                });
                t_id += 1;
            }
        })
    } else {
        console.log('No facts present: ' + index.index_name)
    }

}

function makeSignificantWordsTables(index) {
    let t_id = 0;
    let rootProperty = index.getSignificantWords()
    /*has to be a number field*/
    let colorRowIndex = 1
    for (let field in rootProperty) {
        let result = formatSignificantWords(index, rootProperty[field])
        if (result != null) {

            let minMax = getColorRange(result, colorRowIndex, index)
            let color = d3.scale.linear()
                .domain([minMax[0], minMax[1]])
                .range([d3.rgb(Colors.COLOR_MIN), d3.rgb(Colors.COLOR_MAX)]);

            let tableID = `${index.AggregationTpes.SIGSTERMS}-generated-${index.index_name}${t_id}`
            $(`#${index.index_name}-sigsterms-table`).append(`<table id="${tableID}" style="width:100%"></table>`);

            $(`#${tableID}`).DataTable({
                data: result,
                dom: 't',
                ordering: true,
                order: [1, 'desc'],
                paging: false,
                columns: [
                    {title: field},
                    {title: "count"}
                ],
                "rowCallback": function (row, data, index) {
                    $($(row).children()[colorRowIndex]).css('background-color', color(data[colorRowIndex]))
                }
            });
            t_id += 1;
        }
    }
}

function makeFrequentItemsTables(index) {
    let t_id = 0;
    let rootProperty = index.getFrequentItems()
    /*has to be a number field*/
    let colorRowIndex = 1
    for (let field in rootProperty) {
        let result = formatFrequentItems(index, rootProperty[field])

        if (result != null) {
            let minMax = getColorRange(result, colorRowIndex, index)
            let color = d3.scale.linear()
                .domain([minMax[0], minMax[1]])
                .range([d3.rgb(Colors.COLOR_MIN), d3.rgb(Colors.COLOR_MAX)]);

            let tableID = `${index.AggregationTpes.STERMS}-generated-${index.index_name}${t_id}`
            $(`#${index.index_name}-sterms-table`).append(`<table id="${tableID}" style="width:100%"></table>`);

            $(`#${tableID}`).DataTable({
                data: result,
                dom: 't',
                ordering: true,
                order: [1, 'desc'],
                paging: false,
                columns: [
                    {title: field},
                    {title: "count"}
                ],
                "rowCallback": function (row, data, index) {
                    $($(row).children()[colorRowIndex]).css('background-color', color(data[colorRowIndex]))
                }
            });
            t_id += 1;
        }
    }
}

function makeStatistics(index) {
    let response = formatStatistics(index);
    /*has to be a number field*/
    let colorRowIndex = 2
    if (response) {
        let minMax = findMinMax(response, colorRowIndex, index)

        let color = d3.scale.linear()
            .domain([0, minMax[1]])
            .range([d3.rgb(Colors.COLOR_MIN), d3.rgb(Colors.COLOR_MAX)]);

        let tableID = `${index.AggregationTpes.VALUECOUNT}-generated-${index.index_name}`;
        $(`#${index.index_name}-value_count-table`).append(`<table id="${tableID}" style="width:100%"></table>`);
        $(`#${tableID}`).DataTable({
            data: response,
            dom: 't',
            ordering: true,
            order: [1, 'desc'],
            paging: false,
            columns: [
                {title: "field"},
                {title: "count"},
                {title: "percentage"}
            ],
            "rowCallback": function (row, data, index) {
                $($(row).children()[colorRowIndex]).css('background-color', color(data[colorRowIndex]))
            }
        });

    }

}

function formatFrequentItems(index, field) {
    /* datatables parsable format */

    if (checkNested(field, 'buckets')) {
        let result = (field.buckets.map((e) => {
            return [e.key, e.doc_count]
        }));
        return index.filterTerms(result)
    } else {
        console.error('formatFrequentItems, properties did not match expected format')
        return []
    }
}

function formatSignificantWords(index, field) {
    /* datatables parsable format */

    if (checkNested(field, 'buckets')) {
        let result = (field.buckets.map((e) => {
            return [e.key, e.doc_count]
        }));
        return index.filterTerms(result)
    } else {
        console.error('formatSignificantWords, properties did not match expected format')
        return []
    }
}

function formatStatistics(index) {
    let data = index.getStatistics();

    let result = [];
    for (let f in data) {
        result.push([f, data[f].value, data[f].percentage])
    }

    return result;
}

function formatFacts(index) {
    /* todo:this*/
    let root = index.getFacts()
    if (checkNested(root, 'texta_facts', 'sterms#fact_category', 'buckets')) {
        return (root.texta_facts['sterms#fact_category'].buckets.map((e) => {
            return {"key": e.key, "facts": e['sigsterms#significant_facts'].buckets}
        }));
    }
}

function findMinMax(arr, indexToParse) {
    let min = arr[0][indexToParse], max = arr[0][indexToParse];

    for (let i = 1, len = arr.length; i < len; i++) {
        let v = arr[i][indexToParse];
        min = (v < min) ? v : min;
        max = (v > max) ? v : max;
    }

    return [min, max];
}

function getColorRange(source, colorCellIndex, index) {
    if (colorSetting === ColorSettings.GLOBAL) {
        return [0, index.total_documents]
    } else if (colorSetting === ColorSettings.FIELD) {
        return findMinMax(source, colorCellIndex)
    }
}

function getHiddenDivMaxWidth(elementID) {
    /*disgusting hack to get hidden element width*/
    let cloneID = `${elementID}_cloned`
    let clonedTimelineContainer = $(`#${elementID}`).clone()
    clonedTimelineContainer.attr('id', cloneID)
    clonedTimelineContainer.addClass('timeline-clone')
    $('.page-wrapper').append(clonedTimelineContainer)
    let width = $('#' + cloneID).width()
    clonedTimelineContainer.remove()
    return width
}