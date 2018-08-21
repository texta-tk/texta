import psycopg2

from dataset_importer.utils import HandleDatasetImportException


class PostgreSQLReader(object):

    @staticmethod
    def get_features(**kwargs):

        try:
            host = kwargs.get('postgres_host', None)
            database = kwargs.get('postgres_database', None)
            port = kwargs.get('postgres_port', None)
            user = kwargs.get('postgres_user', None)
            password = kwargs.get('postgres_password', None)
            table_name = kwargs.get('postgres_table', None)

            connection_string = PostgreSQLReader.get_connection_string(host, database, port, user, password)

            with psycopg2.connect(connection_string) as connection:
                cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
                cursor.execute("SELECT * FROM %s;" % table_name)

                value = cursor.fetchone()
                while value:
                    yield value
                    value = cursor.fetchone()

        except Exception as e:
            HandleDatasetImportException(kwargs, e, file_path='')

    @staticmethod
    def count_total_documents(**kwargs):
        raise NotImplementedError()

    @staticmethod
    def get_connection_string(host, database, port, user, password):
        string_parts = []

        if host:
            string_parts.append("host=" + host)
        if database:
            string_parts.append("dbname=" + database)
        if port:
            string_parts.append("port=" + str(port))
        if user:
            string_parts.append("user=" + user)
        if password:
            string_parts.append("password=" + password)

        return ' '.join(string_parts)