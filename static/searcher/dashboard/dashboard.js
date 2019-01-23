var PREFIX = LINK_SEARCHER;


$(function () {
    console.log(PREFIX);
    $.get(PREFIX + '/dashboard', function (data) {
        let indices = [];

        if (checkNested(data, 'indices')) {
            console.table(data.indices);
            data.indices.forEach((element) => {
                indices.push(new Index(element.aggregations, element.index_name, element.total_documents))
            })
        }
        initListeners();
        initDashBoard(indices)
    });
});

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
        makeTimeline(e);
        makeStermsTables(e);
        makeSigstermsTables(e);
        makeFactsTables(e);
        makeStatistics(e);
    })
}

function makeStatistics(index) {
    let response = formatStatistics(index);
    if (response) {
        let tableID = `${index.AggregationTpes.VALUECOUNT}-generated-${index.index_name}`;
        $('#' + index.index_name + '-value_count-table').append(`<table id="${tableID}" style="width:100%"></table>`);
        $(`#${tableID}`).DataTable({
            data: response,
            dom: 't',
            ordering: true,
            order: [1, 'desc'],
            paging: false,
            columns: [
                {title: "field"},
                {title: "percentage"},
                {title: "count"}
            ]
        });

    }

}

function makeTimeline(index) {
    let div = document.getElementById('timeline-agg-container-' + index.index_name);
    let dates = index.getDates();

    if (dates) {
        let xData = dates.map((e) => e.key_as_string);
        let yData = dates.map((e) => e.doc_count);
        Plotly.plot(div, [{
            x: xData,
            y: yData
        }], {
            margin: {t: 0}
        });
    } else {
        div.remove()
    }
}

function makeFactsTables(index) {
    let result = formatFacts(index)

    if (result) {
        let t_id = 0;
        /*nested*/
        result.forEach((e) => {
            let result = e.facts.map((x) => {
                return [x.key, x.doc_count]
            });
            let minMax = findMinMax(result)

            let color = d3.scale.linear()
                .domain([minMax[0], minMax[1]])
                .range([d3.rgb("#bfffc4"), d3.rgb('#02e012')]);
            let tableID = `${index.AggregationTpes.NESTED}-generated-${index.index_name}${t_id}`
            $('#' + index.index_name + '-nested-table').append(`<table id="${tableID}" style="width:100%"><caption>${e.key}</caption></table>`);

            $(`#${tableID}`).DataTable({
                data: result,
                dom: 't',
                ordering: true,
                order: [1, 'desc'],
                paging: false,
                columns: [
                    {title: "facts"},
                    {title: "count"}
                ],
                "rowCallback": function (row, data, index) {
                    $($(row).children()[1]).css('background-color', color(data[1]))
                }
            });
            t_id += 1;
        })
    } else {
        console.log('No facts present: ' + index.index_name)
    }

}

function makeSigstermsTables(index) {
    let t_id = 0;
    let rootProperty = index.getSigsterms()
    for (let field in rootProperty) {
        let result = formatSigsterms(index, rootProperty[field])
        if (result != null) {
            let minMax = findMinMax(result)

            let color = d3.scale.linear()
                .domain([minMax[0], minMax[1]])
                .range([d3.rgb("#bfffc4"), d3.rgb('#02e012')]);

            let tableID = `${index.AggregationTpes.SIGSTERMS}-generated-${index.index_name}${t_id}`
            $('#' + index.index_name + '-sigsterms-table').append(`<table id="${tableID}" style="width:100%"></table>`);

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
                    $($(row).children()[1]).css('background-color', color(data[1]))
                }
            });
            t_id += 1;
        }
    }
}

function makeStermsTables(index) {
    let t_id = 0;
    let rootProperty = index.getSterms()
    for (let field in rootProperty) {
        let result = formatSterms(index, rootProperty[field])

        if (result != null) {
            let minMax = findMinMax(result)

            let color = d3.scale.linear()
                .domain([minMax[0], minMax[1]])
                .range([d3.rgb("#bfffc4"), d3.rgb('#02e012')]);

            let tableID = `${index.AggregationTpes.STERMS}-generated-${index.index_name}${t_id}`
            $('#' + index.index_name + '-sterms-table').append(`<table id="${tableID}" style="width:100%"></table>`);

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
                    $($(row).children()[1]).css('background-color', color(data[1]))
                }
            });
            t_id += 1;
        }
    }
}

function formatSterms(index, field) {
    /* datatables parsable format */

    if (checkNested(field, 'buckets')) {
        let result = (field.buckets.map((e) => {
            return [e.key, e.doc_count]
        }));
        return index.filterTerms(result)
    } else {
        console.error('formatSterms, properties did not match expected format')
        return []
    }
}

function formatSigsterms(index, field) {
    /* datatables parsable format */

    if (checkNested(field, 'buckets')) {
        let result = (field.buckets.map((e) => {
            return [e.key, e.doc_count]
        }));
        return index.filterTerms(result)
    } else {
        console.error('formatSigsterms, properties did not match expected format')
        return []
    }
}

function formatStatistics(index) {
    let data = index.getStatistics();

    let result = [];
    for (let f in data) {
        result.push([f, data[f].percentage, data[f].value])
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


function findMinMax(arr) {
    let min = arr[0][1], max = arr[0][1];

    for (let i = 1, len=arr.length; i < len; i++) {
        let v = arr[i][1];
        min = (v < min) ? v : min;
        max = (v > max) ? v : max;
    }

    return [min, max];
}
/*ex data structure*/
/*    var data = {
        "name": "A1",
        "children": [
            {
                "name": "B1",
                "children": [
                    {
                        "name": "C1",
                        "value": 100
                    },
                    {
                        "name": "C2",
                        "value": 300
                    },
                    {
                        "name": "C3",
                        "value": 200
                    }
                ]
            },
            {
                "name": "B2",
                "value": 200
            }
        ]
    };*/

/*  this is for d3 things, acceptable hiearchy format
    var tempList = []

    index.getFacts()['sterms#fact_category'].buckets.forEach((e) => {
        tempList.push({
            'key': e.key,
            'children': e['sigsterms#significant_facts'].buckets
        })
    })

    console.log(tempList)
    var temp = {
        "key": 'FACTS',
        "children" : tempList
    }*/