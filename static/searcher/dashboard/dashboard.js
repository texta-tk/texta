var PREFIX = LINK_SEARCHER;

function display_aggregation_timeline() {
    $.get(PREFIX + '/dashboard', function (data) {
        $("#timeline-agg-container").empty();
        drawTimeline(data.aggregations.kuupaev_bucket.buckets);
    });
}

function drawTimeline(dates) {
    new Morris.Line({
        // ID of the element in which to draw the chart.
        element: 'timeline-agg-container',
        // Chart data records -- each entry in this array corresponds to a point on
        // the chart.
        data: dates,
        // The name of the data record attribute that contains x-values.
        xkey: 'key_as_string',
        // A list of names of data record attributes that contain y-values.
        ykeys: ['doc_count'],
        // Labels for the ykeys -- will be displayed when you hover over the
        // chart.
        labels: ["Search Documents"],

        dateFormat: function (x) { return new Date(x).toString(); },
        xLabels: ['year'],
        xLabelAngle: 45,
      });
}
