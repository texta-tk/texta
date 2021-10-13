#! /usr/bin/env python3
import json
import os

from toolkit.settings import UAA_AUTHORIZE_URI, UAA_CLIENT_ID, UAA_LOGOUT_URI, UAA_OAUTH_TOKEN_URI, UAA_PROJECT_ADMIN_SCOPE, UAA_REDIRECT_URI, UAA_SCOPES, UAA_URL, USE_UAA


# Parse env variables
TEXTA_API_URL = os.getenv("TEXTA_API_URL", "http://localhost")
TEXTA_HOSTED_FILE_FIELD = os.getenv("TEXTA_HOSTED_FILE_FIELD", "properties.hosted_filepath")

# Generate config

config = {
    "apiHost": TEXTA_API_URL,
    "apiBasePath": "/api/v2",
    "logging": True,
    "fileFieldReplace": TEXTA_HOSTED_FILE_FIELD,
    "useCloudFoundryUAA": USE_UAA,
    "uaaConf": {
        "uaaURL": f"{UAA_URL}",
        "redirect_uri": UAA_REDIRECT_URI,
        "logout_uri": UAA_LOGOUT_URI,
        "authorize_uri": UAA_AUTHORIZE_URI,
        "client_id": UAA_CLIENT_ID,
        "scope": UAA_SCOPES,
        "admin_scope": UAA_PROJECT_ADMIN_SCOPE,
        "response_type": "code",
    }
}
# print output
print(json.dumps(config))
