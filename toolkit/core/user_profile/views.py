from django.contrib.auth.models import User
from rest_framework import mixins, viewsets

from toolkit.core.user_profile.serializers import UserSerializer
from toolkit.permissions.project_permissions import UserIsAdminOrReadOnly


class UserViewSet(mixins.RetrieveModelMixin,
                  mixins.ListModelMixin,
                  mixins.UpdateModelMixin,
                  mixins.DestroyModelMixin,
                  viewsets.GenericViewSet):
    """
    list: Returns list of users.
    read: Returns user details by id.
    update: can update superuser status.
    """

    serializer_class = UserSerializer
    # Disable default pagination
    pagination_class = None
    permission_classes = (UserIsAdminOrReadOnly,)


    def get_queryset(self):
        queryset = User.objects.all().order_by('-date_joined')
        current_user = self.request.user
        if not current_user.is_superuser:
            queryset = queryset.filter(id=self.request.user.id)
        return queryset


    def update(self, request, *args, **kwargs):
        instance = self.get_object()
        if request.user == instance:
            request.data.pop("is_superuser")
        return super(UserViewSet, self).update(request, *args, **kwargs)
