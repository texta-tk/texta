import sqlite3


class SQLiteIndex(object):

    def __init__(self, sqlite_file_path):
        self._sqlite_file_path = sqlite_file_path
        self._active_datasets = {}

    def add(self, dataset, values):
        with sqlite3.connect(self._sqlite_file_path) as connection:
            table_name = self._get_dataset_table_name(dataset)
            connection.execute('CREATE TABLE IF NOT EXISTS {0}(id TEXT PRIMARY KEY);'.format(table_name))
            connection.executemany('INSERT INTO {0} VALUES (?);'.format(table_name), ((value,) for value in values))

    def get_new_entries(self, dataset, candidate_values):
        with sqlite3.connect(self._sqlite_file_path) as connection:
            connection.row_factory = scalar_factory
            table_name = self._get_dataset_table_name(dataset)

            if not self._table_exists(table_name=table_name):
                return candidate_values

            temp_table_name = self._get_temporary_table_name(dataset)
            cursor = connection.cursor()
            cursor.execute('CREATE TEMPORARY TABLE IF NOT EXISTS {0}(id TEXT PRIMARY KEY);'.format(temp_table_name))
            cursor.executemany('INSERT INTO {0} VALUES (?);'.format(temp_table_name),
                               ((value,) for value in candidate_values))
            cursor.execute('SELECT id FROM {0} EXCEPT SELECT id FROM {1};'.format(temp_table_name, table_name))
            return cursor.fetchall()

    def remove(self, dataset):
        with sqlite3.connect(self._sqlite_file_path) as connection:
            table_name = self._get_dataset_table_name(dataset)
            connection.execute("DROP TABLE IF EXISTS {0};".format(table_name))

    def _get_dataset_table_name(self, dataset):
        return 'es_{0}'.format(dataset)

    def _get_temporary_table_name(self, dataset):
        return 'es_{0}_temp'.format(dataset)

    def _table_exists(self, table_name):
        with sqlite3.connect(self._sqlite_file_path) as connection:
            cursor = connection.cursor()
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='{0}';".format(table_name))
            return bool(cursor.fetchone())


def scalar_factory(cursor, row):
    return row[0]
