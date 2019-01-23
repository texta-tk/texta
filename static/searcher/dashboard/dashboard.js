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
        makeSTERMSTables(e);
        makeSIGSTERMSTables(e);
        makeFACTSTables(e);
        makeStatistics(e);

    })
}
function makeStatistics(index){
    let response = index.getVALUECOUNT()
    console.log(response)
    for (let f in response){
        console.log(f)
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

function makeFACTSTables(index) {
    let result = formatFACTS(index)

    if (result) {
        let t_id = 0;
        result.forEach((e) => {
            let result = e.facts.map((x) => {
                return [x.key, x.doc_count]
            });
            $('#' + index.index_name + '-nested-table').append(`<table id="${index.AggregationTpes.NESTED}-generated-${index.index_name}${t_id}" style="width:100%"><caption>${e.key}</caption></table>`);

            $(`#${index.AggregationTpes.NESTED}-generated-${index.index_name}${t_id}`).DataTable({
                data: result,
                dom: 't',
                ordering: true,
                order: [1, 'desc'],
                paging: false,
                columns: [
                    {title: "facts"},
                    {title: "count"}
                ]
            });
            t_id += 1;
        })
    } else {
        console.log('No facts present: '+index.index_name)
    }


}

function makeSIGSTERMSTables(index) {
    let t_id = 0;
    for (let field in index.aggregations[index.AggregationTpes.SIGSTERMS]) {
        let result = formatSIGSTERMS(index, field)

        if (result != null) {
            $('#' + index.index_name + '-sigsterms-table').append(`<table id="${index.AggregationTpes.SIGSTERMS}-generated-${index.index_name}${t_id}" style="width:100%"></table>`);

            $(`#${index.AggregationTpes.SIGSTERMS}-generated-${index.index_name}${t_id}`).DataTable({
                data: result,
                dom: 't',
                ordering: true,
                order: [1, 'desc'],
                paging: false,
                columns: [
                    {title: field},
                    {title: "count"}
                ]
            });
            t_id += 1;
        }
    }
}

function makeSTERMSTables(index) {
    let t_id = 0;
    for (let field in index.aggregations[index.AggregationTpes.STERMS]) {
        let result = formatSTERMS(index, field)

        if (result != null) {
            $('#' + index.index_name + '-sterms-table').append(`<table id="${index.AggregationTpes.STERMS}-generated-${index.index_name}${t_id}" style="width:100%"></table>`);

            $(`#${index.AggregationTpes.STERMS}-generated-${index.index_name}${t_id}`).DataTable({
                data: result,
                dom: 't',
                ordering: true,
                order: [1, 'desc'],
                paging: false,
                columns: [
                    {title: field},
                    {title: "count"}
                ]
            });
            t_id += 1;
        }
    }
}

function formatSTERMS(index, field) {
    /* datatables parsable format */
    let root = index.getSTERMS()
    if (checkNested(root, field, 'buckets')) {
        let result = (root[field].buckets.map((e) => {
            return [e.key, e.doc_count]
        }));
        return filterResults(result)
    } else {
        console.error('formatSTERMS, properties did not match expected format')
        return []
    }
}

function formatSIGSTERMS(index, field) {
    /* datatables parsable format */
    let root = index.getSIGSTERMS()
    if (checkNested(root, field, 'buckets')) {
        let result = (root[field].buckets.map((e) => {
            return [e.key, e.doc_count]
        }));
        return filterResults(result)
    } else {
        console.error('formatSIGSTERMS, properties did not match expected format')
        return []
    }
}

function formatFACTS(index) {
    /* todo:this*/
    let result = []
    let root = index.getFACTS()
    if (checkNested(root, ['sterms#fact_category'], 'buckets')) {
        result = (root['sterms#fact_category'].buckets.map((e) => {
            return {"key": e.key, "facts": e['sigsterms#significant_facts'].buckets}
        }));
    }

    /* filter out garbage */
    return filterResults(result)
}

function filterResults(result) {
    let notAllowedToEnterHeaven = []
    result.filter((e) => {
        if (e[1] < 50) {
            notAllowedToEnterHeaven.push(e[1])
        }
    });

    if (notAllowedToEnterHeaven.length < 3 && result.length > 3) {
        return result;
    }
    return null;
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

    index.getFACTS()['sterms#fact_category'].buckets.forEach((e) => {
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