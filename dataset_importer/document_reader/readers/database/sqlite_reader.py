import sqlite3
import os
import fnmatch


class SQLiteReader(object):

    @staticmethod
    def get_features(**kwargs):
        select_query = kwargs['sqlite_select_query']
        directory = kwargs['directory']

        for file_path in SQLiteReader.get_file_list(root_directory=directory):
            with sqlite3.connect(file_path) as connection:
                connection.row_factory = dict_factory
                cursor = connection.cursor()
                cursor.execute(select_query)

                value = cursor.fetchone()
                while value:
                    yield value
                    value = cursor.fetchone()

    @staticmethod
    def count_total_documents(**kwargs):
        directory = kwargs['directory']
        count_query = kwargs['sqlite_count_query']

        total_count = 0

        for file_path in SQLiteReader.get_file_list(root_directory=directory):
            with sqlite3.connect(file_path) as connection:
                cursor = connection.cursor()
                cursor.execute(count_query)

                total_count += cursor.fetchone()[0]

    @staticmethod
    def get_file_list(root_directory):
        matches = []
        for directory, directory_names, file_names in os.walk(root_directory):
            for filename in fnmatch.filter(file_names, '*.sqlite3'):
                matches.append(os.path.join(directory, filename))

        return matches


def dict_factory(cursor, row):
    """Transforms retrieved data into dicts representing rows.
    """
    dict_ = {}
    for idx, col in enumerate(cursor.description):
        dict_[col[0]] = row[idx]
    return dict_
