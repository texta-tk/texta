var PREFIX = LINK_SEARCHER;



$(function() {
    console.log(PREFIX)
    $.get(PREFIX + '/dashboard', function (data) {
        let indices = []

        if(checkNested(data, 'indices')){
            console.table(data.indices)
            data.indices.forEach((element)=>{
                indices.push(new Index(element.aggregations, element.index_name, element.total_documents))
            })
        }
        initDashBoard(indices)
    });
});

function initDashBoard(indices){
    //timelines
    indices.forEach((e)=>{
        drawTimeline(e)
    })
}

function drawTimeline(index) {
    let div = document.getElementById('timeline-agg-container-'+index.index_name);
    let dates = index.getDates()

    if (dates){
        let xData = dates.map((e)=> e.key_as_string)
        let yData = dates.map((e)=> e.doc_count)
        Plotly.plot( div, [{
            x: xData,
            y: yData }], {
            margin: { t: 0 } } );
    }else{
        div.remove()
    }
}