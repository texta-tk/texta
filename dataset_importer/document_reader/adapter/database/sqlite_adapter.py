import sqlite3


class SQLiteAdapter(object):

    @staticmethod
    def get_features(file_path=None, table_name=None):
        with sqlite3.connect(file_path) as connection:
            connection.row_factory = dict_factory
            cursor = connection.cursor()
            cursor.execute("SELECT * FROM %s;" % table_name)

            value = cursor.fetchone()
            while value:
                yield value
                value = cursor.fetchone()


def dict_factory(cursor, row):
    """Transforms retrieved data into dicts representing rows.
    """
    dict_ = {}
    for idx, col in enumerate(cursor.description):
        dict_[col[0]] = row[idx]
    return dict_
