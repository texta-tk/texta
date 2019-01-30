from functools import update_wrapper

from django.contrib.admin import AdminSite
from django.contrib.auth import REDIRECT_FIELD_NAME
from django.urls import reverse
from django.http import HttpResponseRedirect
from django.views.decorators.cache import never_cache
from django.views.decorators.csrf import csrf_protect

from texta.settings import URL_PREFIX_RESOURCE


def admin_view(self, view, cacheable=False):
    """
    Decorator to create an admin view attached to this ``AdminSite``. This
    wraps the view and provides permission checking by calling
    ``self.has_permission``.

    You'll want to use this from within ``AdminSite.get_urls()``:

        class MyAdminSite(AdminSite):

            def get_urls(self):
                from django.conf.urls import url

                urls = super(MyAdminSite, self).get_urls()
                urls += [
                    url(r'^my_view/$', self.admin_view(some_view))
                ]
                return urls

    By default, admin_views are marked non-cacheable using the
    ``never_cache`` decorator. If the view can be safely cached, set
    cacheable=True.
    """
    def inner(request, *args, **kwargs):
        if not self.has_permission(request):
            if request.path == reverse('admin:logout', current_app=self.name):
                index_path = reverse('admin:index', current_app=self.name)
                return HttpResponseRedirect(URL_PREFIX_RESOURCE + index_path)
            # Inner import to prevent django.contrib.admin (app) from
            # importing django.contrib.auth.models.User (unrelated model).
            from django.contrib.auth.views import redirect_to_login
            return redirect_to_login(
                request.get_full_path(),
                reverse('admin:login', current_app=self.name)
            )
        return view(request, *args, **kwargs)
    if not cacheable:
        inner = never_cache(inner)
    # We add csrf_protect here so this function can be used as a utility
    # function for any view, without having to repeat 'csrf_protect'.
    if not getattr(view, 'csrf_exempt', False):
        inner = csrf_protect(inner)
    return update_wrapper(inner, view)


@never_cache
def login(self, request, extra_context=None):
    """
    Displays the login form for the given HttpRequest.
    """
    if request.method == 'GET' and self.has_permission(request):
        # Already logged-in, redirect to admin index
        index_path = reverse('admin:index', current_app=self.name)
        return HttpResponseRedirect(URL_PREFIX_RESOURCE+index_path)

    from django.contrib.auth.views import login
    # Since this module gets imported in the application's root package,
    # it cannot import models from other applications at the module level,
    # and django.contrib.admin.forms eventually imports User.
    from django.contrib.admin.forms import AdminAuthenticationForm
    context = dict(self.each_context(request),
        title= ('Log in'),
        app_path=request.get_full_path(),
    )
    if REDIRECT_FIELD_NAME not in request.GET and REDIRECT_FIELD_NAME not in request.POST:
        context[REDIRECT_FIELD_NAME] = request.get_full_path()
    context.update(extra_context or {})

    defaults = {
        'extra_context': context,
        'current_app': self.name,
        'authentication_form': self.login_form or AdminAuthenticationForm,
        'template_name': self.login_template or 'admin/login.html',
    }
    return login(request, **defaults)


AdminSite.admin_view = admin_view
AdminSite.login = login
