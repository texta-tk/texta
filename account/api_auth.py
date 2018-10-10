
import json

from django.http import HttpResponse
from account.models import Profile


class api_auth:
    """ API Authentication Decorator
    """

    def __init__(self, call_method):
        self.call_method = call_method

    def _api_token_auth(self, auth_token):
        try:
            profile = Profile.objects.get(auth_token=auth_token)
            user = profile.user
            valid_token = True
        except Profile.DoesNotExist:
            user = None
            valid_token = False
        return user, valid_token

    def unauthorized(self):
        error = {'error': 'not authorized'}
        data_json = json.dumps(error)
        return HttpResponse(data_json, status=403, content_type='application/json')

    def __call__(self, request):
        try:
            request_data = request.body.decode("utf-8")
            params = json.loads(request_data)
            auth_token = params.get('auth_token', None)
            user, valid_token = self._api_token_auth(auth_token)

            if valid_token and user is not None:
                # Log auth ok
                # Callback wrapper
                _return = self.call_method(request, user, params)
                return _return
            else:
                # Not authorized
                # TODO: log invalid auth ?
                return self.unauthorized()
        except Exception as e:
            # Something went wrong...
            # TODO: log exception info ?
            print(e)
            error = {'error': 'invalid request'}
            data_json = json.dumps(error)
            return HttpResponse(data_json, status=400, content_type='application/json')
