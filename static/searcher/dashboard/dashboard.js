var PREFIX = LINK_SEARCHER;



$(function() {
    console.log(PREFIX);
    $.get(PREFIX + '/dashboard', function (data) {
        let indices = [];

        if(checkNested(data, 'indices')){
            console.table(data.indices);
            data.indices.forEach((element)=>{
                indices.push(new Index(element.aggregations, element.index_name, element.total_documents))
            })
        }
        initListeners();
        initDashBoard(indices)
    });
});
function initListeners(){
    let previous = '';
    $('#index_fields').on('change', function() {
        console.log(this.value);
        if(previous === ''){
            $(`#datatables-container-${this.value}`).removeClass('hidden');
            previous = this.value
        }else{
            $(`#datatables-container-${previous}`).addClass('hidden');
            $(`#datatables-container-${this.value}`).removeClass('hidden');
            previous = this.value
        }
    });
}
function initDashBoard(indices){
    //timelines
    indices.forEach((e)=>{
        makeTimeline(e);
        makeTables(e)
    })
}

function makeTimeline(index) {
    let div = document.getElementById('timeline-agg-container-'+index.index_name);
    let dates = index.getDates();

    if (dates){
        let xData = dates.map((e)=> e.key_as_string);
        let yData = dates.map((e)=> e.doc_count);
        Plotly.plot( div, [{
            x: xData,
            y: yData }], {
            margin: { t: 0 } } );
    }else{
        div.remove()
    }
}
function makeTables(index){
    // todo: fix all of this, make it better

    for (let field in index.aggregations.sterms){
        let columnName = field;
        let sterms =( index.aggregations.sterms[field].buckets.map((e)=>{

            return [e.key, e.doc_count]

        }));
        let notAllowedToEnterHeaven = []
        sterms.filter((e)=>{
            if(e[1] <50){
                notAllowedToEnterHeaven.push(e[1])
            }
        })

        if(sterms.length > 5 && notAllowedToEnterHeaven.length <3){
            $('#datatables-container-'+index.index_name).append(`<table id="generated-${field}" style="width:100%"></table>`);
            console.table(sterms);
            $('#generated-'+field).DataTable( {
                data: sterms,
                dom: 't',
                ordering: true,
                order: [ 1, 'desc' ],
                paging: false,
                columns: [
                    { title: columnName },
                    { title: "Key" }
                ]
            } );
        }
    }
}