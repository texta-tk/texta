""" Check facts structure in Elasticsearch
"""
import json
import sys
import time

import requests


class Progress:
    def __init__(self, total, wait=0.5):
        self.n_total = total
        self.n_count = 0
        self.last_update = 0
        self.wait_time = wait

    def update(self, count, and_show=True):
        self.n_count = count
        if and_show:
            self.show()

    def show(self, force_show=False):
        now = time.time()
        if now < (self.last_update + self.wait_time) and not force_show:
            return
        self.last_update = now
        BAR_SIZE = 20
        p = (1.0 * self.n_count) / self.n_total
        p = 1.0 if p > 1.0 else p
        total = int((BAR_SIZE * p))
        f = '#' * total
        e = ' ' * (BAR_SIZE - total)
        bar = '\r [{0}] - {1:3.0f} %   '.format(f + e, 100 * p)
        sys.stdout.write(bar)
        sys.stdout.flush()

    def done(self):
        self.update(self.n_total, and_show=False)
        self.show(force_show=True)
        print '\n'


class CheckCritical(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


class CheckError(Exception):
    def __init__(self, msg):
        self.msg = msg

    def __str__(self):
        return self.msg


def check(func):

    def func_wrapper(*args, **kwargs):
        instance = args[0]
        try:
            if not instance.critical_status():
                instance.check_total_error()
                instance.count_tests += 1
                func(*args, **kwargs)

        except CheckError as e:
            msg = e.msg
            instance.maybe_print('ERROR', msg)
            instance.errors.append(msg)
        except CheckCritical as e:
            msg = e.msg
            instance.maybe_print('ERROR', msg)
            instance.errors.append(msg)
            instance.flag_critical_error()
        except:
            print('-- Unexpected error:')
            for k in sys.exc_info():
                print('{0}'.format(k))
            instance.flag_critical_error()

    return func_wrapper


class FactsCheck:

    TEXTA = 'texta'

    MAX_ERROR_MSG = 50
    MAX_WARNING_MSG = 200

    def __init__(self, es_url, _index, verbose=True):
        self.es_url = es_url
        self._index = _index
        self.warnings = []
        self.errors = []
        self.verbose = verbose
        self.count_tests = 0
        self.total_facts = 0
        self._critical = False

    def check_total_error(self):
        if len(self.errors) >= self.MAX_ERROR_MSG:
            error_msg = 'Maximum number of errors exceeded'
            raise CheckCritical(error_msg)
        if len(self.warnings) >= self.MAX_WARNING_MSG:
            error_msg = 'Maximum number of warnings exceeded'
            raise CheckCritical(error_msg)

    def flag_critical_error(self):
        self._critical = True

    def critical_status(self):
        return self._critical

    def maybe_print(self, status, msg):
        if self.verbose:
            # If executed from tty, add some colors!
            if sys.stdout.isatty():
                attr = ['1']
                if status == 'ERROR':
                    attr.append('31')
                if status == 'OK':
                    attr.append('32')
                if status == 'WARNING':
                    attr.append('33')
                status = '\x1b[{0}m{1}\x1b[0m'.format(';'.join(attr), status)
            text = '[{0}] - {1}'.format(status, msg)
            print(text)

    @check
    def check_version(self):
        request_url = '{0}'.format(self.es_url)
        response = requests.get(request_url).json()
        ver = response['version']['number']
        self.maybe_print('OK', 'ES version {0}'.format(ver))

    @check
    def check_index_present(self):
        request_url = '{0}/_aliases'.format(self.es_url)
        response = requests.get(request_url).json()
        indexes = response.keys()
        if self._index not in indexes:
            error_msg = 'Index {0} was not found'.format(self._index)
            raise CheckCritical(error_msg)

        self.maybe_print('OK', 'Index {0} is present'.format(self._index))

    @check
    def check_if_has_texta_mapping(self):
        request_url = '{0}/{1}'.format(self.es_url, self._index)
        response = requests.get(request_url).json()
        mappings = response[self._index]['mappings']
        if self.TEXTA not in mappings:
            error_msg = 'Mapping [{0}] was not found'.format(self.TEXTA)
            raise CheckCritical(error_msg)

        self.maybe_print('OK', 'Mapping [{0}] is present'.format(self.TEXTA))

    @check
    def check_number_facts(self):
        total = self._get_total_facts()
        if total == 0:
            error_msg = 'The total of facts is zero'
            raise CheckCritical(error_msg)

        self.maybe_print('OK', 'Total of [{0}] facts'.format(total))

    @check
    def check_facts_structure(self):
        count_total = 0
        for hit in self._get_fact_hits():
            count_total += 1
            _id = hit['_id']
            fact = hit['_source']
            if 'facts' not in fact:
                error_msg = 'Fact _id:{0} does not have [facts]'.format(_id)
                raise CheckError(error_msg)
            fact_body = fact['facts']
            for k in ['doc_type', 'fact', 'doc_path', 'doc_id', 'spans']:
                if k not in fact_body:
                    error_msg = 'Fact _id:{0} does not have [{1}]'.format(_id, k)
                    raise CheckError(error_msg)

        self.maybe_print('OK', 'Facts structure looks ok [{0}]'.format(count_total))

    @check
    def _check_types(self, _id, fact):
        # All are strings, except 'doc_id'
        for k in ['doc_type', 'fact', 'doc_path', 'spans']:
            v = fact[k]
            if not isinstance(v, basestring):
                error_msg = 'Fact _id:{0}  [{1}] is not string'.format(_id, k)
                raise CheckError(error_msg)

    @check
    def _check_element(self, _id, fact):
        doc_type = fact['doc_type']
        fact_name = fact['fact']
        doc_path = fact['doc_path']
        doc_id = fact['doc_id']
        spans = fact['spans']

        if len(fact_name) == 0:
            error_msg = 'Fact _id:{0} has empty fact_name'.format(_id)
            raise CheckError(error_msg)

        if len(fact_name) > 20:
            warning_msg = 'Fact _id:{0} has long fact_name'.format(_id)
            self._set_warning(warning_msg)

        request_url = 'http://localhost:9200/{0}/{1}/{2}'.format(self._index, doc_type, doc_id)
        response = requests.get(request_url).json()
        if not response['found']:
            error_msg = 'Fact _id:{0} has an invalid document [doc_id:{1}]'.format(_id, doc_id)
            raise CheckError(error_msg)

        try:
            spans = json.loads(spans)
            assert isinstance(spans, list)
        except Exception:
            error_msg = 'Fact _id:{0} has invalid spans field '.format(_id)
            raise CheckError(error_msg)

        len_spans = len(spans)
        if len_spans == 0:
            warning_msg = 'Fact _id:{0} has empty spans'.format(_id)
            self._set_warning(warning_msg)

        doc = response['_source']
        path_parts = doc_path.split('.')

        try:
            for p in path_parts:
                doc = doc[p]
        except KeyError:
            error_msg = 'Fact _id:{0} has invalid doc_path [doc_path:{1}]'.format(_id, doc_path)
            raise CheckError(error_msg)

        len_field = len(doc) + 1
        max_span = max([s[1] for s in spans])
        if max_span > len_field:
            warning_msg = 'Fact _id:{0} has likely a wrong span'.format(_id)
            self._set_warning(warning_msg)

    @check
    def check_facts_association(self):
        self.maybe_print('--', 'Checking facts associations ...')
        n_count = 0
        n_total = self._get_total_facts()
        prog = Progress(n_total)
        for hit in self._get_fact_hits():
            n_count += 1
            prog.update(n_count)
            _id = hit['_id']
            fact = hit['_source']['facts']
            self._check_types(_id, fact)
            self._check_element(_id, fact)
        prog.done()
        self.maybe_print('--', 'Done [{0}]'.format(n_count))

    def _set_warning(self, msg):
        self.warnings.append(msg)
        self.maybe_print('WARNING', msg)

    def _check_es_error(self, r):
        # Check errors in the database request
        if (r['_shards']['total'] > 0 and r['_shards']['successful'] == 0) or r['timed_out']:
            msg_base = 'Elasticsearch: *** Shards: {0} *** Timeout: {1} *** Took: {2}'
            msg = msg_base.format(r['_shards'], r['timed_out'], r['took'])
            raise CheckCritical(msg)

    def _get_fact_hits(self):
        scroll_url = '{0}/_search/scroll?scroll=1m'.format(self.es_url)
        search_url = '{0}/{1}/{2}/_search?search_type=scan&scroll=1m&size=100'.format(self.es_url, self._index, self.TEXTA)
        query = {u'query': {u'bool': {u'should': [], u'must': []}}}
        q = json.dumps(query)
        response = requests.post(search_url, data=q).json()
        scroll_id = response['_scroll_id']
        total_msg = response['hits']['total']
        while total_msg > 0:
            response = requests.post(scroll_url, data=scroll_id).json()
            scroll_id = response['_scroll_id']
            total_msg = len(response['hits']['hits'])
            self._check_es_error(response)
            for hit in response['hits']['hits']:
                yield hit

    def _get_total_facts(self):
        request_url = 'http://localhost:9200/{0}/{1}/_count'.format(self._index, self.TEXTA)
        response = requests.post(request_url).json()
        return response['count']

    def check_all(self):
        self.check_version()
        self.check_index_present()
        self.check_if_has_texta_mapping()
        self.check_number_facts()
        self.check_facts_structure()
        self.check_facts_association()

    def summary(self):
        if self.critical_status():
            print ('\n ... stopped because a critical error has happened ... \n')
        else:
            print('\nSummary:\n')

        print('\tTotal of errors:   \t{0}'.format(len(self.errors)))
        print('\tTotal of warnings: \t{0}'.format(len(self.warnings)))
        print('\tExecuted tests: \t{0}'.format(self.count_tests))


def main():
    arguments = sys.argv
    if len(arguments) != 3 and len(arguments) != 2:
        print('Wrong number of arguments. Use one of those:')
        print('\t1) python {0} --indexes'.format(arguments[0]))
        print('\t2) python {0} index'.format(arguments[0]))
        print('\t3) python {0} index port'.format(arguments[0]))
        print('')
        return

    _index = arguments[1]
    _port = arguments[2] if len(arguments) == 3 else 9200
    es_url = 'http://localhost:{0}'.format(_port)

    if _index == '--indexes':
        request_url = '{0}/_aliases'.format(es_url)
        response = requests.get(request_url).json()
        for k in response.keys():
            print k
        return

    print('Starting... {0}/{1} \n'.format(es_url, _index))
    start_time = time.time()
    check = FactsCheck(es_url, _index)
    check.check_all()
    check.summary()
    end_time = time.time()
    print '\n... total time: {0:2.2f} [min]'.format((end_time-start_time)/60.0)

if __name__ == '__main__':
    main()
