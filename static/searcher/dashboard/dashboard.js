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
    //timelines
    indices.forEach((e) => {
        makeTimeline(e);
        makeSTERMSTables(e);
        makeSIGSTERMSTables(e);
        makeFACTSTables(e);
    })
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
    let t_id = 0;
    for (let field in index.aggregations[index.AggregationTpes.NESTED]) {
        let result = formatFACTS(index, field)

        if (result != null) {
            $('#' + index.index_name + '-nested-table').append(`<table id="${index.AggregationTpes.NESTED}-generated-${index.index_name}${t_id}" style="width:100%"></table>`);

            $(`#${index.AggregationTpes.NESTED}-generated-${index.index_name}${t_id}`).DataTable({
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
    let result = (index.aggregations[index.AggregationTpes.STERMS][field].buckets.map((e) => {
        /*Stuff to display in datatables, change columns titles accordingly*/
        return [e.key, e.doc_count]
    }));

    /* filter out garbage */
    return filterResults(result)
}

function formatSIGSTERMS(index, field) {
    /* datatables parsable format */
    let result = (index.aggregations[index.AggregationTpes.SIGSTERMS][field].buckets.map((e) => {
        return [e.key, e.doc_count]
    }));

    /* filter out garbage */
    return filterResults(result)
}

function formatFACTS(index, field) {
    /* datatables parsable format */
    let result = []
    for (let facts in index.aggregations[index.AggregationTpes.NESTED][field]) {
        if (checkNested(index.aggregations[index.AggregationTpes.NESTED][field], facts, 'buckets')) {
            result = (index.aggregations[index.AggregationTpes.NESTED][field][facts].buckets.map((e) => {
                return [e.key, e.doc_count]
            }));
        }


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