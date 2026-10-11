from rest_framework.pagination import PageNumberPagination


class StandardResultsSetPagination(PageNumberPagination):
    """Default pagination used by every list endpoint.

    The client may override the page size with the ``page_size`` query
    parameter, capped by ``max_page_size``.
    """

    page_size = 20
    page_size_query_param = "page_size"
    max_page_size = 100
