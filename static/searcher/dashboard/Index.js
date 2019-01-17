class Index {
    constructor(aggregations, index_name, total_documents) {
        this.aggregations = aggregations;
        this.index_name = index_name;
        this.total_documents = total_documents;
    }

    getDates() {
        if(checkNested(this.aggregations, 'date_histogram','kuupaev_year','buckets')){
            return this.aggregations.date_histogram.kuupaev_year.buckets;
        }else{
            console.error(`index named ${this.index_name} does not have date_histogram field!`);
            return undefined
        }

    }
}
function checkNested(obj ) {
    var args = Array.prototype.slice.call(arguments, 1);

    for (var i = 0; i < args.length; i++) {
        if (!obj || !obj.hasOwnProperty(args[i])) {
            return false;
        }
        obj = obj[args[i]];
    }
    return true;
}