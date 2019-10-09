from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class PageNumberPaginationDataOnly(PageNumberPagination):
    ''' Default pagination '''
    page_size_query_param = 'page_size'

    def get_paginated_response(self, data):
        return Response({
            'count': self.page.paginator.count,
            'results': data
        })
