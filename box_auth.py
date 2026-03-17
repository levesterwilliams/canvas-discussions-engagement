# box_auth.py
# Author: Levester Williams
# Date: 16 Mar 2026
#
# Script to gain access to BOX API


import os
import requests
from json_freader import JSONfreader

TOKEN_URL = "https://api.box.com/oauth2/token"

def get_box_access_token():
    reader = JSONfreader()
    creds = reader.load_json_file("box_api_cred.json")
    payload = {
        "grant_type": "refresh_token",
        "refresh_token": creds["BOX_REFRESH_TOKEN"],
        "client_id": creds["BOX_CLIENT_ID"],
        "client_secret": creds["BOX_CLIENT_SECRET"]
    }
    print(f"CLIENT ID: {payload["client_id"]}")
    print(f"CLIENT Secret: {payload["client_secret"]}")
    response = requests.post(TOKEN_URL, data=payload)

    print("STATUS:", response.status_code)
    print("RESPONSE:", response.text)
    try:
        data = response.json()
    except RuntimeError or KeyError:
        raise RuntimeError("Box API key failed")

    if "access_token" not in data:
        raise RuntimeError("Failed to obtain Box access token")

    return data["access_token"]
