# box_upload.py
# Author: Levester Williams
# Date: 16 March 2026

"""Box file transfer helpers for generated Excel reports and config files."""

import json
from pathlib import Path

import requests

from shared.box_auth import BoxAuthManager


BOX_UPLOAD_URL = "https://upload.box.com/api/2.0/files/content"
BOX_DOWNLOAD_URL_TEMPLATE = "https://api.box.com/2.0/files/{file_id}/content"


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


def download_file_from_box(file_id: str, destination_path: str | Path) -> Path:
    """Download a Box file to a local path.

    Parameters
    ----------
    file_id : str
        Fixed Box file ID for the source file.
    destination_path : str or pathlib.Path
        Local path where the downloaded file should be written.

    Returns
    -------
    pathlib.Path
        Local path to the downloaded file.

    Raises
    ------
    RuntimeError
        Raised when the Box API rejects the download.

    Notes
    -----
    Authentication is delegated to :class:`shared.box_auth.BoxAuthManager`.
    """
    local_path = Path(destination_path)
    local_path.parent.mkdir(parents=True, exist_ok=True)

    auth = BoxAuthManager(json_file="box_api_cred.json")
    token = auth.get_valid_access_token()
    headers = {"Authorization": f"Bearer {token}"}
    download_url = BOX_DOWNLOAD_URL_TEMPLATE.format(file_id=file_id)

    with requests.get(download_url, headers=headers, stream=True, timeout=60) as response:
        if response.status_code != 200:
            raise RuntimeError(f"Box download failed: {response.status_code} {response.text}")

        with local_path.open("wb") as file_handle:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    file_handle.write(chunk)

    return local_path