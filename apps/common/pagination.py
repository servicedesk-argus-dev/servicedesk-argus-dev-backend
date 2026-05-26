from rest_framework.pagination import PageNumberPagination
from rest_framework.response import Response


class DefaultPagination(PageNumberPagination):
    page_size = 25
    page_size_query_param = "limit"
    max_page_size = 200

    def get_paginated_response(self, data):
        return Response(
            {
                "success": True,
                "data": data,
                "pagination": {
                    "total": self.page.paginator.count,
                    "pages": self.page.paginator.num_pages,
                    "current": self.page.number,
                    "next": self.get_next_link(),
                    "previous": self.get_previous_link(),
                },
            }
        )

