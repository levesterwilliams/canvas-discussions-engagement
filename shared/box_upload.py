# box_upload.py
# Author: Levester Williams
# Date: 16 March 2026

"""Box upload helpers for generated Excel reports."""

import json
from pathlib import Path

import requests

from shared.box_auth import BoxAuthManager


BOX_UPLOAD_URL = "https://upload.box.com/api/2.0/files/content"


def upload_file_to_box(local_file_path: str | Path, folder_id: str) -> str:
    """Upload a local file to a Box folder.

    Parameters
    ----------
    local_file_path : str or pathlib.Path
        Path to the file that should be uploaded.
    folder_id : str
        Box folder identifier that will receive the upload.

    Returns
    -------
    str
        Box file ID returned by the upload API.

    Raises
    ------
    FileNotFoundError
        Raised when ``local_file_path`` does not exist.
    RuntimeError
        Raised when the Box API rejects the upload or returns an
        unexpected payload.

    Notes
    -----
    Authentication is delegated to :class:`shared.box_auth.BoxAuthManager`.
    """
    file_path = Path(local_file_path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    auth = BoxAuthManager(json_file="box_api_cred.json")
    token = auth.get_valid_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    attributes = {
        "name": file_path.name,
        "parent": {"id": str(folder_id)},
    }

    with file_path.open("rb") as file_handle:
        response = requests.post(
            BOX_UPLOAD_URL,
            headers=headers,
            files={
                "attributes": (None, json.dumps(attributes)),
                "file": (file_path.name, file_handle),
            },
            timeout=60,
        )

    if response.status_code not in (200, 201):
        raise RuntimeError(f"Box upload failed: {response.status_code} {response.text}")

    try:
        data = response.json()
        return str(data["entries"][0]["id"])
    except (ValueError, KeyError, IndexError) as exc:
        raise RuntimeError(f"Unexpected response format from Box: {response.text}") from exc



