# box_upload.py
# Author: Levester Williams
# Date: 16 march 2026
#
# Script to upload files to Box


import requests
import os
import json
from box_auth import get_box_access_token

BOX_UPLOAD_URL = "https://upload.box.com/api/2.0/files/content"

def upload_file_to_box(local_file_path, folder_id):
    token = get_box_access_token()
    headers = {'Authorization': 'Bearer ' + token}

    attributes = {
        "name": os.path.basename(local_file_path),
        "parent": {"id": folder_id}
    }

    files = {
        "attributes": (None, json.dumps(attributes)),
        "file": open(local_file_path, 'rb')
    }


    response = requests.post(
        BOX_UPLOAD_URL,
        headers=headers,
        files=files
    )
    print("STATUS:", response.status_code)
    print("RESPONSE:", response.text)

    if response.status_code not in (200, 201):
        raise Exception("box upload failed")

    data = response.json()

    if "entries" not in data:
        raise Exception(f"Unexpected response format: {data}")
    print("uploaded to Box: " + response.json()["entries"][0]["id"])



