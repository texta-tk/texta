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
        console.log(this.value);
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
function makeSIGSTERMSTables(index){
    for (let field in index.aggregations[index.AggregationTpes.SIGSTERMS]) {
        let result = index.formatSIGSTERMS(field)

        if (result != null) {
            $('#'+index.index_name+'-sigsterms-table' ).append(`<table id="${index.AggregationTpes.SIGSTERMS}-generated-${field}" style="width:100%"></table>`);
            console.table(result);
            $(`#${index.AggregationTpes.SIGSTERMS}-generated-${field}`).DataTable({
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
        }
    }
}
function makeSTERMSTables(index) {

    for (let field in index.aggregations[index.AggregationTpes.STERMS]) {
        let result = index.formatSTERMS(field)

        if (result != null) {
            $('#'+index.index_name+'-sterms-table' ).append(`<table id="${index.AggregationTpes.STERMS}-generated-${field}" style="width:100%"></table>`);
            console.table(result);
            $(`#${index.AggregationTpes.STERMS}-generated-${field}`).DataTable({
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
        }
    }
}