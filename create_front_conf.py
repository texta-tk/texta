#! /usr/bin/env python3
import json
import os

from toolkit.settings import UAA_SCOPES, USE_UAA, UAA_URL, UAA_REDIRECT_URI, UAA_CLIENT_ID


# Parse env variables
TEXTA_API_URL = os.getenv("TEXTA_API_URL", "http://localhost")
TEXTA_HOSTED_FILE_FIELD = os.getenv("TEXTA_HOSTED_FILE_FIELD", "properties.hosted_filepath")

# Generate config

config = {
    "apiHost": TEXTA_API_URL,
    "apiBasePath": "/api/v1",
    "apiBasePath2": "/api/v2",
    "logging": True,
    "fileFieldReplace": TEXTA_HOSTED_FILE_FIELD,
    "useCloudFoundryUAA": USE_UAA,
    "uaaConf": {
        "uaaURL": f"{UAA_URL}/oauth/authorize",
        "redirect_uri": UAA_REDIRECT_URI,
        "client_id": UAA_CLIENT_ID,
        "scope": UAA_SCOPES,
        "response_type": "code"
    }
}
# print output
print(json.dumps(config))
