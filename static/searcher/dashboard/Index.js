class Index {
    constructor(aggregations, index_name, total_documents) {
        this.aggregations = aggregations;
        this.index_name = index_name;
        this.total_documents = total_documents;
        this.AggregationTpes = {
            "VALUECOUNT": 'value_count',
            "STERMS": 'sterms',
            "SIGSTERMS": 'sigsterms',
            "DATE_HISTOGRAM": 'date_histogram',
            "NESTED": 'nested'
        };
        this.minCountFilter = 50;
        this.minAmountData = 3;
        Object.freeze(this.AggregationTpes);
    }
    getDatesYear() {
        if (checkNested(this.aggregations, this.AggregationTpes.DATE_HISTOGRAM, 'kuupaev_year', 'buckets')) {
            return this.aggregations[this.AggregationTpes.DATE_HISTOGRAM].kuupaev_year.buckets;
        } else {
            console.error(`index ${this.index_name}, does not have date_histogram field!`);
            return undefined
        }
    }
    getDatesMonth() {
        if (checkNested(this.aggregations, this.AggregationTpes.DATE_HISTOGRAM, 'kuupaev_month', 'buckets')) {
            return this.aggregations[this.AggregationTpes.DATE_HISTOGRAM].kuupaev_month.buckets;
        } else {
            console.error(`index ${this.index_name}, does not have date_histogram field!`);
            return undefined
        }
    }
    getFrequentItems(){
        if(checkNested(this.aggregations, this.AggregationTpes.STERMS, )){
            return this.aggregations[this.AggregationTpes.STERMS]
        }else{
            console.error(`index ${this.index_name}, Properties did not match expected format: STERMS!`)
            return undefined
        }
    }
    getSignificantWords(){
        if(checkNested(this.aggregations, this.AggregationTpes.SIGSTERMS, )){
            return this.aggregations[this.AggregationTpes.SIGSTERMS]
        }else{
            console.error(`index ${this.index_name}, Properties did not match expected format: SIGSTERMS!`)
            return undefined
        }
    }
    getFacts(){
        if(checkNested(this.aggregations, this.AggregationTpes.NESTED)){
            return this.aggregations[this.AggregationTpes.NESTED]
        }else{
            console.error(`index ${this.index_name}, Properties did not match expected format: NESTED!`)
        }
    }
    getStatistics(){
        if(checkNested(this.aggregations, this.AggregationTpes.VALUECOUNT )){
            return this.aggregations[this.AggregationTpes.VALUECOUNT]
        }else{
            console.error(`index ${this.index_name}, Properties did not match expected format: VALUECOUNT!`)
        }
    }
    /*so each index can filter seperately if in the future you want to adjust filtering settings for each index */
    filterTerms(result) {
        let notAllowedToEnterHeaven = []
        result.filter((e) => {
            if (e[1] < this.minCountFilter) {
                notAllowedToEnterHeaven.push(e[1])
            }
        });

        if (notAllowedToEnterHeaven.length < this.minAmountData && result.length > this.minAmountData) {
            return result;
        }
        return null;
    }


}

function checkNested(obj) {
    var args = Array.prototype.slice.call(arguments, 1);

    for (var i = 0; i < args.length; i++) {
        if (!obj || !obj.hasOwnProperty(args[i])) {
            console.error('no property: '+args[i])
            console.error('obj: '+args)
            return false;
        }
        obj = obj[args[i]];
    }
    return true;
}