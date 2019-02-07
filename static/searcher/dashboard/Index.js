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
        this.minCountFilter = 0;
        this.minAmountData = 0;
        Object.freeze(this.AggregationTpes);
    }

    getDatesYear() {

        if (this.aggregations[this.AggregationTpes.DATE_HISTOGRAM]) {
            console.error(`index ${this.index_name}, does not have date_histogram field!`);
            return undefined
        } else {
            let keys = Object.keys(this.aggregations[this.AggregationTpes.DATE_HISTOGRAM]);
            let key = keys.filter(function (key) {
                return key.endsWith("_year")
            })[0];

            if (checkNested(this.aggregations, this.AggregationTpes.DATE_HISTOGRAM, key, 'buckets')) {
                return this.aggregations[this.AggregationTpes.DATE_HISTOGRAM][key]['buckets'];
            } else {
                console.error(`index ${this.index_name}, date_histogram no buckets property!`);
                return undefined
            }
        }
    }

    getDatesMonth() {

        if (this.aggregations[this.AggregationTpes.DATE_HISTOGRAM]) {
            console.error(`index ${this.index_name}, does not have date_histogram field!`);
            return undefined

        } else {
            let keys = Object.keys(this.aggregations[this.AggregationTpes.DATE_HISTOGRAM]);
            let key = keys.filter(function (key) {
                return key.endsWith("_month")
            })[0];

            if (checkNested(this.aggregations, this.AggregationTpes.DATE_HISTOGRAM, key, 'buckets')) {
                return this.aggregations[this.AggregationTpes.DATE_HISTOGRAM][key]['buckets'];
            } else {
                console.error(`index ${this.index_name}, date_histogram no buckets property!`);
                return undefined
            }
        }
    }


    getFrequentItems() {
        if (checkNested(this.aggregations, this.AggregationTpes.STERMS)) {
            return this.aggregations[this.AggregationTpes.STERMS]
        } else {
            console.error(`index ${this.index_name}, Properties did not match expected format: STERMS!`)
            return undefined
        }
    }

    getSignificantWords() {
        if (checkNested(this.aggregations, this.AggregationTpes.SIGSTERMS)) {
            return this.aggregations[this.AggregationTpes.SIGSTERMS]
        } else {
            console.error(`index ${this.index_name}, Properties did not match expected format: SIGSTERMS!`)
            return undefined
        }
    }

    getFacts() {
        if (checkNested(this.aggregations, this.AggregationTpes.NESTED)) {
            return this.aggregations[this.AggregationTpes.NESTED]
        } else {
            console.error(`index ${this.index_name}, Properties did not match expected format: NESTED!`)
            return undefined
        }
    }

    getStatistics() {
        if (checkNested(this.aggregations, this.AggregationTpes.VALUECOUNT)) {
            return this.aggregations[this.AggregationTpes.VALUECOUNT]
        } else {
            console.error(`index ${this.index_name}, Properties did not match expected format: VALUECOUNT!`)
            return undefined
        }
    }

    /*so each index can filter seperately if in the future you want to adjust filtering settings for each index */
    filterTerms(result) {
        let filteredResult = result.filter((e) => e[1] > this.minCountFilter);
        if (filteredResult.length > this.minAmountData) {
            return filteredResult;
        }
        return undefined;
    }


}

function checkNested(obj) {
    var args = Array.prototype.slice.call(arguments, 1);

    for (var i = 0; i < args.length; i++) {
        if (!obj || !obj.hasOwnProperty(args[i])) {
            console.error('no property: ' + args[i])
            return false;
        }
        obj = obj[args[i]];
    }
    return true;
}