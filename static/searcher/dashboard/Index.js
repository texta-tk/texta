class Index {
    constructor(aggregations, index_name, total_documents) {
        this.aggregations = aggregations;
        this.index_name = index_name;
        this.total_documents = total_documents;
        this.AggregationTpes = {
            "VALUECOUNT": 'valuecount',
            "STERMS": 'sterms',
            "SIGSTERMS": 'sigsterms',
            "DATE_HISTOGRAM": 'date_histogram',
            "NESTED": 'nested'
        };
        Object.freeze(this.AggregationTpes);
    }

    getDates() {
        if (checkNested(this.aggregations, this.AggregationTpes.DATE_HISTOGRAM, 'kuupaev_year', 'buckets')) {
            return this.aggregations[this.AggregationTpes.DATE_HISTOGRAM].kuupaev_year.buckets;
        } else {
            console.error(`index ${this.index_name}, does not have date_histogram field!`);
            return undefined
        }
    }
    getSTERMS(){
        if(checkNested(this.aggregations, this.AggregationTpes.STERMS, )){
            return this.aggregations[this.AggregationTpes.STERMS]
        }else{
            console.error(`index ${this.index_name}, Properties did not match expected format: STERMS!`)
            return undefined
        }
    }
    getSIGSTERMS(){
        if(checkNested(this.aggregations, this.AggregationTpes.SIGSTERMS, )){
            return this.aggregations[this.AggregationTpes.SIGSTERMS]
        }else{
            console.error(`index ${this.index_name}, Properties did not match expected format: SIGSTERMS!`)
            return undefined
        }
    }
    getFACTS(){
        if(checkNested(this.aggregations, this.AggregationTpes.NESTED, 'texta_facts' )){
            return this.aggregations[this.AggregationTpes.NESTED].texta_facts
        }else{
            console.error(`index ${this.index_name}, Properties did not match expected format: NESTED!`)
        }
    }
    getVALUECOUNT(){
        if(checkNested(this.aggregations, this.AggregationTpes.VALUECOUNT )){
            return this.aggregations[this.AggregationTpes.VALUECOUNT]
        }else{
            console.error(`index ${this.index_name}, Properties did not match expected format: VALUECOUNT!`)
        }
    }



}

function checkNested(obj) {
    var args = Array.prototype.slice.call(arguments, 1);

    for (var i = 0; i < args.length; i++) {
        if (!obj || !obj.hasOwnProperty(args[i])) {
            return false;
        }
        obj = obj[args[i]];
    }
    return true;
}