""" Example script for importing HTML contents into Elasticsearch

>> python html2es.py DIR_HTML_CASES MY_INDEX MY_MAPPING

"""
import json
import os
import sys

import bs4
import nltk
from nltk.stem import SnowballStemmer
import requests


language = 'EN'

stemmer = SnowballStemmer("english")
author_map = {'C': 'Court of Justice',
              'T': 'General Court (pre-Lisbon: Court of First Instance)',
              'F': 'Civil Service Tribunal'
              }


def add_to_elasticsearch(data_str):
    base_url = r'http://127.0.0.1:9200/_bulk'
    response = requests.put(base_url, data=data_str)
    if response.status_code == 400:
        print '-- Not good... '
        print response.text


def bulk_data(data, bulk_size = 100):
    bulk_index = 0
    while bulk_index < len(data):
        bulk = data[bulk_index:bulk_index+bulk_size]
        bulk_index += bulk_size
        yield bulk


def get_conclusion(soup):
    dis = ''
    for p in soup.find_all('p'):
        if 'class' in p.attrs and 'Dispositif' in p.attrs['class'][0]:
            dis += p.text

    return dis if dis else 'NA'


def get_case_language(soup):
    dis = ''
    for p in soup.find_all('p'):
        if 'class' in p.attrs and 'FootnoteLangue' in p.attrs['class'][0]:
            dis += p.text

    return dis if dis else 'NA'


def get_sentences_nltk(text):
    text = text.replace('\n', ' ')
    text = text.replace('\t', ' ')
    sentences = [s.lower() for s in nltk.sent_tokenize(text) if s]
    return sentences


def get_lemma_sentences(sentences):
    lemma_sentences = []
    for s in sentences:
        words = [w for w in nltk.word_tokenize(s) if w]
        w_s = [stemmer.stem(w) for w in words]
        l_s = ' '.join(w_s)
        lemma_sentences.append(l_s)
    return lemma_sentences


def main():

    base_dir = sys.argv[1]
    _index = sys.argv[2]
    _type = sys.argv[3]

    print '- Add documents from: {0}'.format(base_dir)
    print '- ES Index: {0}'.format(_index)
    print '- ES Mapping: {0}'.format(_type)

    # Map html input files
    cases_html_map = {}
    for root, dirs, files in os.walk(base_dir):
        for f in files:
            parts = f.split('.')
            assert len(parts) == 2, '-- wow, that is a bit unexpected ...'
            celex = parts[0]
            if '.html' in f:
                cases_html_map[celex] = os.path.join(root, f)

    print '- Total of documents: {0}'.format(len(cases_html_map.keys()))

    n_total = len(cases_html_map.keys())
    n_count = 0
    for bulk in bulk_data(cases_html_map.keys(), bulk_size=100):
        data = []
        for celex in bulk:
            n_count += 1
            if n_count % (n_total / 10) == 0:
                print 'Total: {0} %'.format(int((100.0 * n_count) / n_total))
            sector = celex[0]
            year = celex[1:5]
            author_index = celex[5]
            descriptor = celex[5:7]
            author = author_map[author_index]
            text = ''
            conclusion = 'NA'
            original_language = 'NA'
            celex_file = cases_html_map[celex]
            with open(celex_file, 'r') as f:
                soup = bs4.BeautifulSoup(f.read(), "html.parser")
                raw = soup.text
                sentences = get_sentences_nltk(raw)
                sentences_lm = get_lemma_sentences(sentences)
                text = ' \n'.join(sentences)
                text_lm = ' \n'.join(sentences_lm)
                conclusion = get_conclusion(soup)
                case_language = get_case_language(soup)

            document = {'celex': celex,
                        'language': language,
                        'year': long(year),
                        'author': author,
                        'descriptor': descriptor,
                        'conclusion': conclusion,
                        'case_language': case_language,
                        'document': {
                            'raw': raw,
                            'text': text,
                            'lemmas': text_lm
                        }}

            index = {"index": {"_index": _index,
                               "_type": _type,
                               "_id": n_count}}
            index = json.dumps(index)
            document = json.dumps(document)
            data.extend([index, document])

        # Add bulk to elastic search
        data_str = '\n'.join(data)
        data_str += '\n'
        add_to_elasticsearch(data_str)

    print 'Done ...'

if __name__ == '__main__':
    main()
