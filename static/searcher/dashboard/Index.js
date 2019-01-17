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
        if (checkNested(this.aggregations, 'date_histogram', 'kuupaev_year', 'buckets')) {
            return this.aggregations.date_histogram.kuupaev_year.buckets;
        } else {
            console.error(`index named ${this.index_name} does not have date_histogram field!`);
            return undefined
        }
    }


    formatSTERMS(field) {
        /* datatables parsable format */
        let result = (this.aggregations[this.AggregationTpes.STERMS][field].buckets.map((e) => {
            return [e.key, e.doc_count]
        }));

        /* filter out garbage */
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
    formatSIGSTERMS(field) {
        /* datatables parsable format */
        let result = (this.aggregations[this.AggregationTpes.SIGSTERMS][field].buckets.map((e) => {
            return [e.key, e.doc_count]
        }));

        /* filter out garbage */
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