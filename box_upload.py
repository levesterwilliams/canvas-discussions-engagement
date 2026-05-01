# box_upload.py
# Author: Levester Williams
# Date: 16 March 2026
#
# Script to upload files to Box


import requests
import os
import json
from box_auth import BoxAuthManager

BOX_UPLOAD_URL = "https://upload.box.com/api/2.0/files/content"

def upload_file_to_box(local_file_path, folder_id):
    """
    Upload a local file to a Box folder.

    This function authenticates with the Box API using a valid access token,
    constructs a multipart/form-data request, and uploads the specified file
    to the given Box folder.

    Parameters
    ----------
    local_file_path : str
        Path to the local file to be uploaded.
    folder_id : str
        The Box folder ID where the file will be uploaded.

    Returns
    -------
    None
        This function does not return a value. On success, it prints the
        uploaded file's Box file ID.

    Raises
    ------
    FileNotFoundError
        If the specified ``local_file_path`` does not exist.
    box_auth.BoxAuthError
        If authentication or token retrieval fails.
    requests.RequestException
        If the HTTP request fails due to network-related issues.
    RuntimeError
        If the Box API response indicates failure or returns an unexpected format.

    Notes
    -----
    - The function uses the Box upload endpoint:
        ``https://upload.box.com/api/2.0/files/content``.
    - A valid OAuth2 access token is required and is obtained via
        ``BoxAuthManager``.
    - The request is sent as ``multipart/form-data`` with file content and
        metadata attributes.
    - Successful responses typically return HTTP status codes 200 or 201.
    """
    auth = BoxAuthManager("box_api_cred.json")
    token = auth.get_valid_access_token()
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

    try:
        data = response.json()
    except ValueError as e:
        raise RuntimeError(
            f"Invalid JSON response from Box: {response.text}"
        ) from e

    if "entries" not in data:
        raise Exception(f"Unexpected response format: {data}")
    print("uploaded to Box: " + response.json()["entries"][0]["id"])



