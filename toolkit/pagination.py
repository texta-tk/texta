from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class PageNumberPaginationDataOnly(PageNumberPagination):
    """ Default pagination """

    def get_paginated_response(self, data):
        return Response(data)


