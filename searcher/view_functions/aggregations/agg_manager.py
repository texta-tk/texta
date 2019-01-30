from utils.datasets import Datasets
from utils.es_manager import ES_Manager
from utils.log_manager import LogManager
from searcher.models import Search
from texta.settings import es_date_format

from dateutil.relativedelta import relativedelta
from datetime import datetime

from collections import defaultdict
import calendar
import json

class AggManager:
    """ Manage Searcher aggregations and plotting preparations
    """
    def __init__(self,request):
        ds = Datasets().activate_datasets(request.session)
        self.es_m = ds.build_manager(ES_Manager)

        # PREPARE AGGREGATION
        self.es_params = request.POST
        interval = self.es_params["interval_1"]


        self.daterange = self._get_daterange(self.es_params)
        
        self.ranges,self.date_labels = self._get_date_intervals(self.daterange,interval)
        self.agg_query = self.prepare_agg_query()
        # EXECUTE AGGREGATION
        agg_results = self.aggregate()

        # PARSE RESPONSES INTO JSON OBJECT
        self.agg_data = self.parse_responses(agg_results)



    @staticmethod
    def _get_daterange(es_params):
        daterange = {"min":es_params["agg_daterange_from_1"],"max":es_params["agg_daterange_to_1"]}
        return daterange


    @staticmethod
    def _get_date_intervals(daterange,interval):
        if daterange['min'] and daterange['max']:
            frmt = "%Y-%m-%d"
            start_datetime = datetime.strptime(daterange['min'],frmt)
            end_datetime = datetime.strptime(daterange['max'],frmt)
        
            if interval == 'year':
                rdelta = relativedelta(years=+1)
            elif interval == 'quarter':
                rdelta = relativedelta(months=+3)
            elif interval == 'month':
                rdelta = relativedelta(months=+1)
            elif interval == 'week':
                rdelta = relativedelta(weeks=+1)
            elif interval == 'day':
                rdelta = relativedelta(days=+1)

            next_calculated_datetime = start_datetime + rdelta
            dates = [start_datetime, next_calculated_datetime]
            labels = [start_datetime.strftime(frmt),next_calculated_datetime.strftime(frmt)]

            while next_calculated_datetime < end_datetime:
                next_calculated_datetime += rdelta
                dates.append(next_calculated_datetime)
                labels.append(next_calculated_datetime.strftime(frmt))

            dates.append(end_datetime)
            labels.append(end_datetime.strftime(frmt))

            dates_str = []
            for i,date in enumerate(dates[1:]):
                dates_str.append({'from':dates[i].strftime(frmt),'to':date.strftime(frmt)})

            return dates_str,labels

        else:

            return [],[]


    def prepare_agg_query(self):
        es_params = self.es_params

        agg_field_1 = es_params["agg_field_1"]
        agg_field_1 = json.loads(agg_field_1)
        sort_by_1 = es_params["sort_by_1"]
        agg_field_2 = es_params["agg_field_2"]
        agg_field_2 = json.loads(agg_field_2)
        sort_by_2 = es_params["sort_by_2"]

        try:
            agg_size_1 = int(es_params["agg_size_1"])        
            agg_size_2 = int(es_params["agg_size_2"])
        except KeyError:
            agg_size_1 = 10
            agg_size_2 = 10

        field_type_to_name = {'date': 'daterange', 'float': 'string', 'string':'string', 'text': 'string', 'keyword': 'string', 'facts': 'fact', 'fact_str_val': 'fact_str_val', 'fact_num_val': 'fact_num_val'}

        agg_name_1 = field_type_to_name[agg_field_1['type']]
        agg_name_2 = field_type_to_name[agg_field_2['type']]

        # If aggregating over text field, use .keyword instead
        if  agg_field_1['type'] == 'text' and sort_by_1 in ['terms', 'significant_terms']:
            agg_field_1['path'] = '{0}.keyword'.format(agg_field_1['path'])
        if  agg_field_2['type'] == 'text' and sort_by_2 in ['terms', 'significant_terms']:
            agg_field_2['path'] = '{0}.keyword'.format(agg_field_2['path'])

        # 1st LEVEL AGGREGATION
        agg = self.create_agg(agg_name_1,sort_by_1,agg_field_1["path"],agg_size_1)

        if agg_name_1 == 'fact' and es_params["agg_field_2_selected"] == 'false':
            agg[agg_name_1]["aggs"][agg_name_1]['aggs']['fact_str_val'] = \
                self.create_agg('fact_str_val', sort_by_1, agg_field_1['path'], agg_size_1)['fact_str_val']['aggs']['fact_str_val']

        # 2nd LEVEL AGGREGATION
        if es_params["agg_field_2_selected"] == 'true':
            agg_2 = self.create_agg(agg_name_2,sort_by_2,agg_field_2["path"],agg_size_2)
            if agg_name_1 == 'fact' and agg_name_2 == 'fact_str_val':
                agg[agg_name_1]['aggs'][agg_name_1]['aggs'] = agg_2[agg_name_2]['aggs']
                agg[agg_name_1]['aggs'][agg_name_1]['aggs']['documents'] = {"reverse_nested": {}}
            elif 'fact' in agg_name_1 and agg_name_2 == 'string':
                agg[agg_name_1]['aggs'][agg_name_1]['aggs']['documents']['aggs'] = agg_2
            else:
                if agg_name_2 == 'fact':
                    agg[agg_name_1]["aggregations"] = agg_2
                    agg[agg_name_1]["aggregations"][agg_name_2]['aggs'][agg_name_2]['aggs'] = self.create_agg('fact_str_val', sort_by_2, agg_field_2['path'], agg_size_2)['fact_str_val']['aggs']
                else:
                    agg[agg_name_1]["aggregations"] = agg_2
        
        return agg


    def create_agg(self, agg_name, sort_by, path, size):
        if agg_name == "daterange":
            return {agg_name: {"date_range": {"field": path, "format": es_date_format, "ranges": self.ranges}}}
        elif agg_name == 'fact':
            return {
                agg_name: {
                    "nested": {"path": "texta_facts"},
                    "aggs": {
                        agg_name: {
                            sort_by: {"field": "texta_facts.fact", "size": size},
                            "aggs": {"documents": {"reverse_nested": {}}}
                        }
                    }
                }
            }
        elif agg_name == 'fact_str_val':
            return {
                agg_name: {
                    "nested": {"path": "texta_facts"},
                    "aggs": {
                        agg_name: {
                            sort_by: {"field": "texta_facts.str_val", "size": size, 'order': {'documents.doc_count': 'desc'}},
                            "aggs": {"documents": {"reverse_nested": {}}}
                        }
                    }
                }
            }
        elif agg_name == 'fact_num_val':
            return {
                agg_name: {
                    "nested": {"path": "texta_facts"},
                    "aggs": {
                        agg_name: {
                            sort_by: {"field": "texta_facts.num_val", "size": size, 'order': {'documents.doc_count': 'desc'}},
                            "aggs": {"documents": {"reverse_nested": {}}}
                        }
                    }
                }
            }
        else:
            return {agg_name: {sort_by: {"field": path, "size": size}}}


    def aggregate(self):
        responses = []
        out = {}

        # EXECUTE SAVED SEARCHES
        for item in self.es_params:
            if 'saved_search' in item:
                s = Search.objects.get(pk=self.es_params[item])
                name = s.description
                saved_query = json.loads(s.query)
                self.es_m.load_combined_query(saved_query)
                self.es_m.set_query_parameter("aggs", self.agg_query)
                response = self.es_m.search()
                responses.append({"id":"search_"+str(s.pk),"label":name,"response":response})
        
        # EXECUTE THE LIVE QUERY
        if "ignore_active_search" not in self.es_params:
            self.es_m.build(self.es_params)
            self.es_m.set_query_parameter("aggs", self.agg_query)
            self.es_m.set_query_parameter("size", 0)
            response = self.es_m.search()
            #raise Exception(self.es_m.combined_query['main']['aggs'])
            responses.append({"id":"query","label":"Current Search","response":response})

        out["responses"] = responses

        # EXECUTE EMPTY TIMELINE QUERY IF RELATIVE FREQUENCY SELECTED     
        if json.loads(self.es_params["agg_field_1"])["type"] == "date" and self.es_params["freq_norm_1"] == "relative_frequency":
            empty_params = {}
            self.es_m.build(empty_params)
            self.es_m.set_query_parameter("aggs", self.agg_query)
            response = self.es_m.search()
            out["empty_timeline_response"] = response
        
        return out


    def parse_responses(self,agg_results):
        """ Parses ES responses into JSON structure and normalises daterange frequencies if necessary
        """

        total_freqs = {}
        agg_data = []

        if "empty_timeline_response" in agg_results:
            for bucket in agg_results["empty_timeline_response"]["aggregations"]["daterange"]["buckets"]:
                total_freqs[bucket["from_as_string"]] = bucket["doc_count"]

        for i,response in enumerate(agg_results["responses"]):
            aggs = response["response"]["aggregations"]
            output_type = None
            response_out = []

            for agg_name,agg_results in aggs.items():
                output_type = agg_name

                if agg_name == 'daterange':
                    response_out.extend(self._parse_daterange_buckets(agg_results['buckets'], total_freqs, self.es_params['freq_norm_1']))
                elif agg_name == 'string':
                    response_out.extend(self._parse_string_buckets(agg_results['buckets']))
                elif agg_name == 'fact':
                    response_out.extend(self._parse_fact_buckets(agg_results['fact']['buckets']))
                elif agg_name == 'fact_str_val' or agg_name == 'fact_num_val':
                    response_out.extend(self._parse_fact_buckets(agg_results[agg_name]['buckets']))

            agg_data.append({"data":response_out,"type":output_type,"label":response["label"]})

        return agg_data
        
    def _parse_daterange_buckets(self, buckets, total_freqs, freq_norm_1):
        results = []

        for bucket in buckets:
            new = {"children":[]}
            new["key"] = bucket["from_as_string"]
            # Normalises frequencies
            if freq_norm_1 == "relative_frequency":
                try:
                    new["val"] = str(round(float(bucket["doc_count"])/float(total_freqs[bucket["from_as_string"]]),5))
                except ZeroDivisionError:
                    new["val"] = 0
            else:
                new["val"] = bucket["doc_count"]

            if "string" in bucket:
                for bucket_2 in bucket["string"]["buckets"]:
                    child = {}
                    child["key"] = bucket_2["key"]
                    child["val"] = bucket_2["doc_count"]
                    new["children"].append(child)
            elif 'fact' in bucket:
                for inner_bucket in bucket['fact']['fact']['buckets']:
                    child = {'key': inner_bucket['key'], 'val': inner_bucket['doc_count']}
                    grandchildren = []
                    for super_inner_bucket in inner_bucket['fact_str_val']['buckets']:
                        grandchildren.append({'key': super_inner_bucket['key'], 'val': super_inner_bucket['documents']['doc_count']})

                    child['children'] = grandchildren
                    new['children'].append(child)
            elif 'fact_str_val' in bucket:
                for inner_bucket in bucket['fact_str_val']['fact_str_val']['buckets']:
                    new['children'].append({'key': inner_bucket['key'], 'val': inner_bucket['documents']['doc_count']})

            results.append(new)

        return results

    def _parse_string_buckets(self, buckets):
        results = []

        for bucket in buckets:
            new = {"children":[]}

            new["key"] = bucket["key"]
            new["val"] = bucket["doc_count"]

            if "string" in bucket:
                for bucket_2 in bucket["string"]["buckets"]:
                    child = {}
                    child["key"] = bucket_2["key"]
                    child["val"] = bucket_2["doc_count"]
                    new["children"].append(child)
            elif 'fact' in bucket:
                for inner_bucket in bucket['fact']['fact']['buckets']:
                    child = {'key': inner_bucket['key'], 'val': inner_bucket['doc_count']}
                    grandchildren = []
                    for super_inner_bucket in inner_bucket['fact_str_val']['buckets']:
                        grandchildren.append({'key': super_inner_bucket['key'], 'val': super_inner_bucket['documents']['doc_count']})

                    child['children'] = grandchildren
                    new['children'].append(child)
            elif 'fact_str_val' in bucket:
                for inner_bucket in bucket['fact_str_val']['fact_str_val']['buckets']:
                    new['children'].append({'key': inner_bucket['key'], 'val': inner_bucket['documents']['doc_count']})

            results.append(new)

        return results

    def _parse_fact_buckets(self, buckets):
        results = []

        for bucket in buckets:
            new = {"children": []}

            new["key"] = bucket["key"]
            new["val"] = bucket["documents"]["doc_count"]

            if 'fact_str_val' in bucket:
                for inner_bucket in bucket['fact_str_val']['buckets']:
                    child = {}
                    child['key'] = inner_bucket['key']
                    child['val'] = inner_bucket['documents']['doc_count']
                    new['children'].append(child)

            elif 'documents' in bucket and 'string' in bucket['documents']:
                for inner_bucket in bucket['documents']['string']['buckets']:
                    child = {}
                    child['key'] = inner_bucket['key']
                    child['val'] = inner_bucket['doc_count']
                    new['children'].append(child)

            results.append(new)

        return results


    def _parse_fact_val_results(self, buckets):
        pass

    def output_to_searcher(self):
        count_dict = defaultdict(defaultdict)
        children_dict = defaultdict(dict)
        i = 0

        data_out = []

        for agg in self.agg_data:
            if agg["type"] == "daterange":
                i+=1
                for row in agg["data"]:
                    count_dict[row["key"]][i] = row["val"]
                    if row["children"]:
                        children_dict[row["key"]][i] = {"data":row["children"],"label":agg["label"]}
            else:
                data_out.append(agg)

        combined_daterange_data = []
        labels = [a["label"] for a in self.agg_data]
        
        for row in sorted(count_dict.items(),key=lambda l:l[0]):
            new_row = dict(row[1])
            new_row["date"] = row[0]
            combined_daterange_data.append(new_row)

        daterange_data = {"type":"daterange",
                          "data":combined_daterange_data,
                          "ykeys":list(range(1,i+1)),
                          "labels":labels,
                          "children":dict(children_dict)}

        if daterange_data["data"]:
            data_out.append(daterange_data)

        return data_out
