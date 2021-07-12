from typing import List

import requests
from django.contrib.auth.models import User
from rest_framework import status
from rest_framework.authtoken.models import Token
from rest_framework.exceptions import APIException, AuthenticationFailed, ValidationError

from toolkit.settings import UAA_URL, USE_UAA


def validate_uaa_setup():
    if USE_UAA is True:
        return True
    else:
        raise APIException("UAA is not configured within settings! Please enable it through the env variable 'TEXTA_USE_UAA'!")


def get_uaa_user_and_token(request):
    user: User = request.user
    if user.profile.is_uaa_account:
        token = Token.objects.get(user=user)
        return user, token
    else:
        return None, None


def get_texta_groups_user_belongs_to(token, user):
    parameters = {
        "filter": f'displayName sw "texta"',
        "attributes": "displayName,members,id"
    }
    response = make_uaa_request(bearer_token=token, endpoint="Groups", parameters=parameters)
    user_id = user.profile.uaa_account_id
    group_list = response.get("resources", [])
    scopes = [
        {"displayName": group["displayName"], "id": group["id"]} for group in group_list if user_id in [
            user["value"] for user in group["members"]
        ]
    ]
    return scopes


def get_users_inside_uaa_group(bearer_token, group_id):
    response = make_uaa_request(bearer_token=bearer_token, endpoint=f"Groups/{group_id}/members?", parameters={"returnEntities": True})
    container = []
    for user in response:
        entity_type = user["type"]
        # Groups can also have other groups.
        if entity_type == "USER":
            entity_content = user["entity"]
            container.append(entity_content)
    return container


def create_django_users(users: List[dict], project_obj) -> int:
    for user in users:
        # TODO This section is duplicated inside uaa_auth.views, make it reusable.
        username = user["userName"]
        emails = [email["value"] for email in user["emails"]]
        email = emails[0] if emails else ""
        name_dict = user.get("name", {})
        first_name = name_dict.get("givenName", None)
        last_name = name_dict.get("familyName", None)

        user_obj, is_created = User.objects.get_or_create(username=username)
        user_obj.profile.uaa_account_id = user["id"]
        user_obj.profile.is_uaa_account = True

        if first_name: user_obj.profile.first_name = first_name
        if last_name: user_obj.profile.last_name = last_name
        if email: user_obj.email = email

        user_obj.profile.save()
        user_obj.save()

        project_obj.users.add(user_obj)

    return len(users)


# TODO Maybe this should be a separate helper for ALL the UAA communications.
def make_uaa_request(bearer_token, endpoint, domain=UAA_URL, parameters={}) -> List[dict]:
    url = f"{domain}/{endpoint}"
    headers = {"Authorization": f"Bearer {bearer_token}"}
    response = requests.get(url, headers=headers, params=parameters)
    if response.status_code == status.HTTP_403_FORBIDDEN:
        raise AuthenticationFailed("Could not connect to UAA, is your token still legitimate?")
    elif response.status_code == status.HTTP_400_BAD_REQUEST:
        raise ValidationError("UAA returned HTTP400, is the request structured properly?")
    elif response.ok:
        return response.json()
    else:
        return []
