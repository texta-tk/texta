import json

from rest_framework import permissions

from toolkit.core.project.models import Project
from toolkit.settings import UAA_PROJECT_ADMIN_SCOPE, USE_UAA


"""
    Only superusers can create new projects
    All project users can perform SAFE and UNSAFE_METHODS on project resources.
"""


# Everyone except a plebian user.
class AuthorProjAdminSuperadminAllowed(permissions.BasePermission):
    message = 'Only authors, superusers and project administrators have access to this resource.'


    def has_permission(self, request, view):
        return self._permission_check(request, view)


    def has_object_permission(self, request, view, obj):
        return self._permission_check(request, view)


    def _permission_check(self, request, view):
        # retrieve project object

        if request.user.is_authenticated is False:
            return False

        try:
            pk = view.kwargs['project_pk'] if "project_pk" in view.kwargs else view.kwargs["pk"]
            project_object = Project.objects.get(id=pk)
        except:
            return False

        if request.user == project_object.author:
            return True

        if request.user in project_object.administrators.all():
            return True

        # check if user is superuser
        if request.user.is_superuser:
            return True

        if USE_UAA:
            user_scopes = json.loads(request.user.profile.scopes)
            if UAA_PROJECT_ADMIN_SCOPE in user_scopes:
                return True

        # nah, not gonna see anything!
        return False


class OnlySuperadminAllowed(permissions.BasePermission):
    message = 'Only superusers have access to this resource.'


    def has_permission(self, request, view):
        return self._permission_check(request, view)


    def has_object_permission(self, request, view, obj):
        return self._permission_check(request, view)


    def _permission_check(self, request, view):
        # retrieve project object

        if request.user.is_authenticated is False:
            return False

        try:
            pk = view.kwargs['project_pk'] if "project_pk" in view.kwargs else view.kwargs["pk"]
            project_object = Project.objects.get(id=pk)
        except:
            return False

        # check if user is superuser
        if request.user.is_superuser:
            return True
        # nah, not gonna see anything!
        return False


# Used inside applications to denote access permissions.
class ProjectAccessInApplicationsAllowed(permissions.BasePermission):
    message = 'Insufficient permissions for this resource.'


    def has_permission(self, request, view):
        return self._permission_check(request, view)


    def has_object_permission(self, request, view, obj):
        return self._permission_check(request, view)


    def _permission_check(self, request, view):

        if request.user.is_authenticated is False:
            return False

        # retrieve project object

        try:
            pk = view.kwargs['project_pk'] if "project_pk" in view.kwargs else view.kwargs["pk"]
            project_object = Project.objects.get(id=pk)
        except:
            return False

        # check if user is superuser
        if request.user.is_superuser:
            return True

        if USE_UAA:
            user_scopes = json.loads(request.user.profile.scopes)
            project_scopes = json.loads(project_object.scopes)

            for project_scope in project_scopes:
                if project_scope in user_scopes:
                    return True

        # check if user is listed among project users
        if request.user in project_object.users.all():
            return True

        if request.user in project_object.administrators.all():
            return True

        # nah, not gonna see anything!
        return False


# Used inside the Project endpoints to manage access to the view itself.
class ProjectEditAccessAllowed(permissions.BasePermission):
    message = 'Insufficient permissions for this project.'


    def has_object_permission(self, request, view, obj):
        return self._permission_check(request, view)


    def _permission_check(self, request, view):


        if request.user.is_authenticated is False:
            return False

        # always permit SAFE_METHODS and superuser
        if request.user.is_superuser:
            return True

        # retrieve project object
        try:
            pk = view.kwargs['project_pk'] if "project_pk" in view.kwargs else view.kwargs["pk"]
            project_object = Project.objects.get(id=pk)
        except:
            return False

        if USE_UAA:
            user_scopes = json.loads(request.user.profile.scopes)
            project_scopes = json.loads(project_object.scopes)

            for project_scope in project_scopes:
                if project_scope in user_scopes:
                    return True

        # Project admins have the right to edit project information.
        if request.user in project_object.administrators.all():
            return True

        # Project users are permitted safe access to project list_view
        if request.user in project_object.users.all() and request.method in permissions.SAFE_METHODS:
            return True

        return False


class IsSuperUser(permissions.BasePermission):

    def has_permission(self, request, view):
        return self._permission_check(request, view)


    def has_object_permission(self, request, view, obj):
        return self._permission_check(request, view)


    def _permission_check(self, request, view):
        return request.user and request.user.is_superuser and request.user.is_authenticated


class ExtraActionAccessInApplications(ProjectAccessInApplicationsAllowed):
    """ Overrides ProjectResourceAllowed for project extra_actions that use POST """


    def _permission_check(self, request, view):
        # retrieve project object

        if request.user.is_authenticated is False:
            return False

        try:
            pk = view.kwargs['project_pk'] if "project_pk" in view.kwargs else view.kwargs["pk"]
            project_object = Project.objects.get(id=pk)
        except:
            return False

        # check if user is superuser
        if request.user.is_superuser:
            return True

        if USE_UAA:
            user_scopes = json.loads(request.user.profile.scopes)
            project_scopes = json.loads(project_object.scopes)

            for project_scope in project_scopes:
                if project_scope in user_scopes:
                    return True

        # check if user is listed among project users
        if request.user in project_object.users.all():
            return True
        if request.user in project_object.administrators.all():
            return True

        # nah, not goa see anything!
        return False


class UserIsAdminOrReadOnly(permissions.BasePermission):
    ''' custom class for user_profile '''


    def has_permission(self, request, view):

        if request.user.is_authenticated is False:
            return False

        if request.method in permissions.SAFE_METHODS:
            return True
        else:
            return request.user.is_superuser


    def has_object_permission(self, request, view, obj):

        if request.user.is_authenticated is False:
            return False

        # can't edit original admin
        if obj.pk == 1 and request.method not in permissions.SAFE_METHODS:
            return False
        if request.method in permissions.SAFE_METHODS:
            return True
        else:
            return request.user.is_superuser
