import psycopg2


class PostgreSQLAdapter(object):

    @staticmethod
    def get_features(host=None, database=None, port=None, user=None, password=None, table_name=None):
        connection_string = PostgreSQLAdapter.get_connection_string(host, database, port, user, password)

        with psycopg2.connect(connection_string) as connection:
            cursor = connection.cursor(cursor_factory=psycopg2.extras.DictCursor)
            cursor.execute("SELECT * FROM %s;" % table_name)

            value = cursor.fetchone()
            while value:
                yield value
                value = cursor.fetchone()

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