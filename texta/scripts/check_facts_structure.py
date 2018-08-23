""" Check facts structure in Elasticsearch
"""
import json
import sys
import time

import requests

import sys
import os.path
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir, 'texta','utils'))) # Add texta.utils temporarily to allow es_manager import 
sys.path.append(
    os.path.abspath(os.path.join(os.path.dirname(__file__), os.pardir))) # Add .. temporarily to allow TEXTA settings import through es_manager

from es_manager import ES_Manager

# Remove temporary paths to avoid future conflicts
sys.path.pop()
sys.path.pop()


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
        p = (1.0 * self.n_count) / self.n_total if self.n_total else 0
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
        response = ES_Manager.plain_get(request_url)
        ver = response['version']['number']
        self.maybe_print('OK', 'ES version {0}'.format(ver))

    @check
    def check_index_present(self):
        request_url = '{0}/_aliases'.format(self.es_url)
        response = ES_Manager.plain_get(request_url)
        indexes = response.keys()
        if self._index not in indexes:
            error_msg = 'Index {0} was not found'.format(self._index)
            raise CheckCritical(error_msg)

        self.maybe_print('OK', 'Index {0} is present'.format(self._index))

    @check
    def check_if_has_texta_mapping(self):
        request_url = '{0}/{1}'.format(self.es_url, self._index)
        response = ES_Manager.plain_get(request_url)
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
            if not isinstance(v, str):
                error_msg = 'Fact _id:{0}  [{1}] is not string'.format(_id, k)
                raise CheckError(error_msg)

    @check
    def _check_element(self, _id, fact):
        doc_type = fact['doc_type']
        fact_name = fact['fact']
        doc_path = fact['doc_path']
        doc_id = fact['doc_id']
        spans = fact['spans']

        # Check fact name size
        if len(fact_name) == 0:
            error_msg = 'Fact _id:{0} has empty fact_name'.format(_id)
            raise CheckError(error_msg)

        # Check fact name with dots
        if '.' in fact_name:
            error_msg = 'Fact _id:{0} contains dot (.) - {1}'.format(_id, fact_name)
            raise CheckError(error_msg)

        # Check fact name max size (warning)
        if len(fact_name) > 100:
            warning_msg = 'Fact _id:{0} has long fact_name'.format(_id)
            self._set_warning(warning_msg)

        # Check doc_id and recover document
        request_url = '{0}/{1}/{2}/{3}'.format(self.es_url, self._index, doc_type, doc_id)
        response = ES_Manager.plain_get(request_url)
        if not response['found']:
            error_msg = 'Fact _id:{0} has an invalid document [doc_id:{1}]'.format(_id, doc_id)
            raise CheckError(error_msg)

        try:
            spans = json.loads(spans)
            assert isinstance(spans, list)
        except Exception:
            error_msg = 'Fact _id:{0} has invalid spans field '.format(_id)
            raise CheckError(error_msg)

        _source = response['_source']

        # Check spans
        len_spans = len(spans)
        if len_spans == 0:
            warning_msg = 'Fact _id:{0} has empty spans'.format(_id)
            self._set_warning(warning_msg)

        # Check doc_path
        doc = _source
        path_parts = doc_path.split('.')
        try:
            for p in path_parts:
                doc = doc[p]
        except KeyError:
            error_msg = 'Fact _id:{0} has invalid doc_path [doc_path:{1}]'.format(_id, doc_path)
            raise CheckError(error_msg)

        # Check fact link
        is_linked = False
        if 'texta_link' not in _source or 'facts' not in _source['texta_link']:
            is_linked = False
        else:
            for fact_link in _source['texta_link']['facts']:
                is_linked = is_linked or (doc_path in fact_link)
        if not is_linked:
            error_msg = 'Fact _id:{0} is not linked with document [doc_id:{1}]'.format(_id, doc_id)
            raise CheckError(error_msg)

        # Check spanned content
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
        response = ES_Manager.plain_post(search_url, data=q)
        scroll_id = response['_scroll_id']
        total_msg = response['hits']['total']
        while total_msg > 0:
            response = ES_Manager.plain_post(scroll_url, data=scroll_id)
            scroll_id = response['_scroll_id']
            total_msg = len(response['hits']['hits'])
            self._check_es_error(response)
            for hit in response['hits']['hits']:
                yield hit

    def _get_total_facts(self):
        request_url = '{0}/{1}/{2}/_count'.format(self.es_url,self._index, self.TEXTA)
        response = ES_Manager.plain_post(request_url)
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


class FactsLink:

    def __init__(self, es_url, _index, _type):
        self.es_url = es_url
        self._index = _index
        self._type = _type
        self.facts_structure = None

    def get_texta_link_facts_by_id(self, doc_id):
        base_url = '{0}/{1}/{2}/{3}?fields=texta_link.facts'
        request_url = base_url.format(self.es_url, self._index, self._type, doc_id)
        response = ES_Manager.plain_get(request_url)
        doc = None
        try:
            if response['found']:
                doc = []
            if 'fields' in response:
                doc = response['fields']['texta_link.facts']
        except KeyError:
            return None
        return doc

    def update_texta_link_by_id(self, doc_id, texta_link):
        base_url = '{0}/{1}/{2}/{3}/_update'
        request_url = base_url.format(self.es_url, self._index, self._type, doc_id)
        d = json.dumps({'doc': texta_link})
        response = ES_Manager.plain_post(request_url, data=d)
        return response

    def get_facts_structure(self):
        base_url = '{0}/{1}/{2}/_search?search_type=scan&scroll=1m&size=100'
        search_url = base_url.format(self.es_url, self._index, 'texta')
        query = {"query": {"term": {"facts.doc_type": self._type.lower()}}}
        query = json.dumps(query)
        response = ES_Manager.plain_post(search_url, data=query)
        scroll_id = response['_scroll_id']
        total = response['hits']['total']
        prog = Progress(total)
        n_count = 0
        facts_structure = {}
        while total > 0:
            response = ES_Manager.plain_post('{0}/_search/scroll?scroll=1m'.format(self.es_url), data=scroll_id)
            total = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']
            for hit in response['hits']['hits']:
                n_count += 1
                prog.update(n_count)
                fact = hit['_source']['facts']['fact']
                doc_path = hit['_source']['facts']['doc_path']
                if fact not in facts_structure:
                    facts_structure[fact] = set()
                facts_structure[fact].add(doc_path)
        prog.done()
        return facts_structure

    def _build_facts_structure(self):
        print 'Build facts structure ...'
        self.facts_structure = self.get_facts_structure()

    def link_all(self):

        self._build_facts_structure()
        print '- Total of unique facts.fact: {0}'.format(len(self.facts_structure.keys()))
        print 'Linking ... '

        search_url_base = '{0}/{1}/{2}/_search?search_type=scan&scroll=1m&size=100'
        search_url = search_url_base.format(self.es_url, self._index, 'texta')

        query = {"query": {"term": {"facts.doc_type": self._type.lower()}}}
        query = json.dumps(query)
        response = ES_Manager.plain_post(search_url, data=query)
        scroll_id = response['_scroll_id']
        total = response['hits']['total']
        n_total = total
        n_count = 0
        prog = Progress(n_total)
        while total > 0:
            response = ES_Manager.plain_post('{0}/_search/scroll?scroll=1m'.format(self.es_url), data=scroll_id)
            total = len(response['hits']['hits'])
            scroll_id = response['_scroll_id']
            for hit in response['hits']['hits']:
                n_count += 1
                prog.update(n_count)

                fact = hit['_source']['facts']['fact']
                doc_path = hit['_source']['facts']['doc_path']
                if fact not in self.facts_structure:
                    self.facts_structure[fact] = set()
                self.facts_structure[fact].add(doc_path)
                fact_link = u'{0}.{1}'.format(doc_path, fact)
                doc_id = hit['_source']['facts']['doc_id']
                links = self.get_texta_link_facts_by_id(doc_id)
                if links is not None:
                    texta_link = {'texta_link': {'facts': links}}
                    if fact_link not in texta_link['texta_link']['facts']:
                        texta_link['texta_link']['facts'].append(fact_link)
                        self.update_texta_link_by_id(doc_id, texta_link)

            # Check errors in the database request
            if (response['_shards']['total'] > 0 and response['_shards']['successful'] == 0) or response['timed_out']:
                msg_base = 'Elasticsearch: *** Shards: {0} *** Timeout: {1} *** Took: {2}'
                msg = msg_base.format(response['_shards'], response['timed_out'], response['took'])
                print msg
        prog.done()


def print_help(commands):
    print('Something went wrong.... valid commands:\n')
    for i,c in enumerate(commands):
        print('{0}) {1}'.format(i+1, c[2]))
    print('')


def main():

    args = sys.argv
    script_name = args[0]
    commands = []
    commands.append(['--indexes', 0, 'python {0} es_url --indexes'.format(script_name)])
    commands.append(['--check', 1, 'python {0} es_url --maps index_name'.format(script_name)])
    commands.append(['--check', 1, 'python {0} es_url --check index_name'.format(script_name)])
    commands.append(['--link', 1, 'python {0} es_url --link index_name map_name'.format(script_name)])
    try:

        c = args[2]
        es_url = args[1]

        if c == '--indexes':
            request_url = '{0}/_aliases'.format(es_url)
            response = ES_Manager.plain_get(request_url)
            for k in response.keys():
                print k
            return

        if c == '--maps':
            _index = u'{0}'.format(args[3])
            request_url = '{0}/{1}'.format(es_url, _index)
            response = ES_Manager.plain_get(request_url).json()
            for k in response[_index]['mappings'].keys():
                print k
            return

        if c == '--check':
            _index = u'{0}'.format(args[3])
            print('Checking... URL: {0}/{1} \n'.format(es_url, _index))
            start_time = time.time()
            check = FactsCheck(es_url, _index)
            check.check_all()
            check.summary()
            end_time = time.time()
            print '\n... total time: {0:2.2f} [min]'.format((end_time - start_time) / 60.0)
            return

        if c == '--link':
            _index = u'{0}'.format(args[3])
            _type = u'{0}'.format(args[4])
            if _type == u'texta':
                raise Exception('Mapping link cant be texta!')
            print('Linking... URL: {0}/{1} - mapping: {2} \n'.format(es_url, _index, _type))
            start_time = time.time()
            link = FactsLink(es_url, _index, _type)
            link.link_all()
            end_time = time.time()
            print '\n... total time: {0:2.2f} [min]'.format((end_time - start_time) / 60.0)
            return

    except Exception as e:
        print '--- Error: {0} \n'.format(e)
    print_help(commands)


if __name__ == '__main__':
    main()
