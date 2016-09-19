from ..utils.datasets import Datasets
from ..utils.es_manager import ES_Manager
from ..utils.log_manager import LogManager
from ..corpus_tool.models import Search
from settings import date_format

from datetime import datetime, timedelta as td
from collections import defaultdict
import calendar
import json

class AggManager:
    """ Manage Searcher aggregations and plotting preparations
    """
    def __init__(self,request):
        ds = Datasets().activate_dataset(request.session)
        self.dataset = ds.get_index()
        self.mapping = ds.get_mapping()
        self.date_range = ds.get_date_range()
        self.es_m = ES_Manager(self.dataset, self.mapping, self.date_range)

        self.ranges,self.date_labels = self.date_ranges(self.es_m.date_range,"month")

        # PREPARE AGGREGATION
        self.es_params = request.POST
        self.agg_query = self.prepare_agg_query()

        # EXECUTE AGGREGATION
        responses = self.aggregate()

        # PARSE RESPONSES INTO DICTS
        self.agg_data = self.parse_responses(responses)


    def prepare_agg_query(self):
        es_params = self.es_params
        
        agg_field_1 = es_params["agg_field_1"]
        agg_field_1 = json.loads(agg_field_1)
        sort_by_1 = es_params["sort_by_1"]
        agg_field_2 = es_params["agg_field_2"]
        agg_field_2 = json.loads(agg_field_2)
        sort_by_2 = es_params["sort_by_2"]
        
        if agg_field_1["type"] == "date":
            agg_name_1 = "daterange"
        else:
            agg_name_1 = "string"

        if agg_field_2["type"] == "date":
            agg_name_2 = "daterange"
        else:
            agg_name_2 = "string"

        # 1st LEVEL AGGREGATION
        agg = self.create_agg(agg_name_1,sort_by_1,agg_field_1["path"])

        # 2nd LEVEL AGGREGATION
        if es_params["agg_field_2_selected"] == 'true':
            agg_2 = self.create_agg(agg_name_2,sort_by_2,agg_field_2["path"])
            agg[agg_name_1]["aggregations"] = agg_2

        return agg


    def create_agg(self,agg_name,sort_by,path):
        if agg_name == "daterange":
            return {agg_name: {"date_range": {"field": path, "format": date_format, "ranges": self.ranges}}}
        else:
            return {agg_name: {sort_by: {"field": path, "size": 20}}}        


    def aggregate(self):
        responses = []

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
        self.es_m.build(self.es_params)
        self.es_m.set_query_parameter("aggs", self.agg_query)
        response = self.es_m.search()
        responses.append({"id":"query","label":"Query","response":response})

        return responses


    def parse_responses(self,responses):
        """ Parses ES responses into dict structure
        """
        agg_data = {0:{},1:{}}
        
        for i,response in enumerate(responses):
            aggs = response["response"]["aggregations"]

            agg_data[0][i] = {"data_dict":defaultdict(int),
                              "key_dict":defaultdict(bool)}
            agg_data[1][i] = {"data_dict":defaultdict(int),
                              "key_dict":defaultdict(bool)}
            
            for agg in aggs.items():               
                for bucket in agg[1]["buckets"]:
                    agg_data[0][i]["data_dict"][bucket["key"]] = bucket["doc_count"]
                    agg_data[0][i]["key_dict"][bucket["key"]] = True

                    # 2nd LEVEL AGG
                    for agg_2 in ["string","daterange"]:
                        try:
                            for bucket_2 in bucket[agg_2]["buckets"]:
                                agg_data[1][i]["data_dict"][bucket_2["key"]] = bucket_2["doc_count"]
                                agg_data[1][i]["key_dict"][bucket_2["key"]] = True
                        except:
                            KeyError

        return agg_data


    def output(self):

        data = self.morris()

#        print data
        
        output = {"morris_data":data,"chart_type":"bar"}

        return output
        

    def morris(self):
        data = []

        print self.agg_data

        for key in self.key_dict.keys():
            row = {"key": key}
            for serie in self.data_dict.keys():
                try:
                    row[serie] = self.data_dict[serie][key]
                except KeyError:
                    row[serie] = 0
            data.append(row)

        ykeys = self.data_dict.keys()

        return {"data":data,"ykeys":ykeys,"labels":ykeys}


    def date_ranges(self,date_range,interval):
        frmt = "%Y-%m-%d"
        
        ranges = []
        labels = []

        date_min = self.convert_date(date_range['min'],frmt)
        date_max = self.convert_date(date_range['max'],frmt)
        
        if interval == 'year':
            for yr in range(date_min.year,date_max.year+1):
                ranges.append({'from':str(yr)+'-01-01','to':str(yr+1)+'-01-01'})
                labels.append(yr)
        if interval == 'quarter':
            for yr in range(date_min.year,date_max.year+1):
                for i,quarter in enumerate([(1,3),(4,6),(7,9),(10,12)]):
                    end = calendar.monthrange(yr,quarter[1])[1]
                    ranges.append({'from':'-'.join([str(yr),str(quarter[0]),'01']),'to':'-'.join([str(yr),str(quarter[1]),str(end)])})
                    labels.append('-'.join([str(yr),str(i+1)+'Q']))
        if interval == 'month':
            for yr in range(date_min.year,date_max.year+1):
                for month in range(1,13):
                    month_max = str(calendar.monthrange(yr,month)[1])
                    if month < 10:
                        month = '0'+str(month)
                    else:
                        month = str(month)
                    ranges.append({'from':'-'.join([str(yr),month,'01']),'to':'-'.join([str(yr),month,month_max])})
                    labels.append('-'.join([str(yr),month]))
        if interval == 'day':
            d1 = date_min
            d2 = date_max+td(days=1)
            delta = d2-d1
            dates = [d1+td(days=i) for i in range(delta.days+1)]
            for date_pair in ngrams(dates,2):
                ranges.append({'from':date_pair[0].strftime(frmt),'to':date_pair[1].strftime(frmt)})
                labels.append(date_pair[0].strftime(frmt))

        return ranges,labels

    def convert_date(self,date_string,frmt):
        return datetime.strptime(date_string,frmt).date()
