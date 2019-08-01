from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response

class PageNumberPaginationDataOnly(PageNumberPagination):
    """ Default pagination """

    def get_paginated_response(self, data):
        return Response(data)

class TaggerGroupsPagination(PageNumberPagination):

    def paginate_queryset(self, queryset, request, view=None):
        page_size = self.get_page_size(request)
        if not page_size:
            return None
        # find the number of all nested tagger elements for tagger_groups_view->
        if len(queryset.values_list('taggers', flat=True)) > page_size:
            page_size = 1
        paginator = self.django_paginator_class(queryset, page_size)
        page_number = request.query_params.get(self.page_query_param, 1)
        if page_number in self.last_page_strings:
            page_number = paginator.num_pages
        try:
            self.page = paginator.page(page_number)
        except InvalidPage as exc:
            msg = self.invalid_page_message.format(
                page_number=page_number, message=str(exc)
            )
            raise NotFound(msg)
        if paginator.num_pages > 1 and self.template is not None:
            # The browsable API should display pagination controls.
            self.display_page_controls = True
        self.request = request
        return list(self.page)

    # render data only, without pagination info in JSON.
    def get_paginated_response(self, data):
        return Response(data)

