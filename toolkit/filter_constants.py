from django.db.models import Q
from django_filters import rest_framework as filters


class FavoriteFilter(filters.FilterSet):
    is_favorited = filters.BooleanFilter(field_name="favorited_users", method="get_is_favorited")


    def get_is_favorited(self, queryset, name, value):
        if value is True:
            return queryset.filter(favorited_users__pk=self.request.user.pk)
        else:
            return queryset.filter(~Q(favorited_users__pk=self.request.user.pk))
