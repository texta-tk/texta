import sqlite3


class SQLiteIndex(object):
    """Implementation of Syncer's index for SQLite. Index is used to identify which documents are already processed.
    """

    def __init__(self, sqlite_file_path):
        self._sqlite_file_path = sqlite_file_path
        self._active_datasets = {}

    def add(self, dataset, values):
        """Adds indexing values (unique strings) to the index.

        :param dataset: name of the dataset for which to store the index values
        :param values: values which are added to the index
        :type dataset: string
        :type value: list of strings
        """
        with sqlite3.connect(self._sqlite_file_path) as connection:
            table_name = self._get_dataset_table_name(dataset)
            connection.execute('CREATE TABLE IF NOT EXISTS {0}(id TEXT PRIMARY KEY);'.format(table_name))
            connection.executemany('INSERT INTO {0} VALUES (?);'.format(table_name), ((value if isinstance(value, unicode) else value.decode('unicode-escape'),) for value in values))

    def get_new_entries(self, dataset, candidate_values):
        """Retrieves index values from candidate index values which are not yet in the dataset's index - in other words
        finds document identifiers which need processing.

        :param dataset: identifier for the dataset/importer job.
        :param candidate_values: document identifiers which are compared against the existing identifiers in the index.
        :type dataset: string
        :type candidate_values: list of strings
        :return: identifiers from candidate_values which are not yet in the index.
        :rtype: string iterator
        """
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
        """Removes dataset's index.

        :param dataset: name of the dataset of which index is to be removed.
        :type dataset: string
        """
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
    """Transforms SQLite's retrieved row to a single value.

    :param cursor: cursor of SQLite's connection.
    :param row: one row of SQLite's select response.
    :return: the first and only element of the index'es select statement response.
    :rtype: string
    """
    return row[0]
