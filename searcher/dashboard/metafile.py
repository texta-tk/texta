import abc


class BaseDashboardConductor(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def query_conductor(self, indices, query_body, elasticsearch, es_url, excluded_fields):
        pass


class BaseDashboardFormater(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def format_result(self, response):
        pass
