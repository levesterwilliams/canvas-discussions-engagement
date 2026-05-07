# box_auth.py
# Author: Levester Williams
# Date: 16 Mar 2026
#
# Script to gain access to BOX API


"""Box authentication helpers for Azure Functions and local execution."""

import json
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path

import requests


class BoxAuthError(Exception):
    """Base exception for Box authentication errors."""


class BoxAuthFileError(BoxAuthError):
    """Raised when credential file operations fail."""


class BoxAuthTokenError(BoxAuthError):
    """Raised when token refresh fails."""


@dataclass
class BoxCredentials:
    """In-memory representation of Box OAuth credentials.

    Attributes
    ----------
    client_id : str
        Box application client ID.
    client_secret : str
        Box application client secret.
    refresh_token : str
        Refresh token used to mint access tokens.
    access_token : str, optional
        Cached access token when available.
    expires_at : int, optional
        Unix timestamp at which the cached access token expires.
    """

    client_id: str
    client_secret: str
    refresh_token: str
    access_token: str = ""
    expires_at: int = 0


class BoxAuthManager:
    """Acquire and refresh Box OAuth access tokens.

    Parameters
    ----------
    json_file : str or None, optional
        Path to a local JSON credential file used as a fallback when
        environment variables are not present.

    Notes
    -----
    In Azure Functions, credentials are expected to come from
    environment variables backed by app settings or Key Vault references.
    """

    def __init__(self, json_file: str | None = None) -> None:
        """Initialize the authentication manager.

        Parameters
        ----------
        json_file : str or None, optional
            Fallback credential file path for local development.
        """
        self._json_file = Path(json_file) if json_file else None
        self._credentials: BoxCredentials | None = None

    def _load_from_env(self) -> BoxCredentials | None:
        """Load Box credentials from environment variables.

        Returns
        -------
        BoxCredentials or None
            Parsed credentials when all required variables are present,
            otherwise ``None``.
        """
        client_id = os.getenv("BOX_CLIENT_ID")
        client_secret = os.getenv("BOX_CLIENT_SECRET")
        refresh_token = os.getenv("BOX_REFRESH_TOKEN")

        if not client_id or not client_secret or not refresh_token:
            return None

        expires_at_raw = os.getenv("BOX_EXPIRES_AT", "0")
        try:
            expires_at = int(expires_at_raw)
        except ValueError:
            expires_at = 0

        return BoxCredentials(
            client_id=client_id,
            client_secret=client_secret,
            refresh_token=refresh_token,
            access_token=os.getenv("BOX_ACCESS_TOKEN", ""),
            expires_at=expires_at,
        )

    def _load_from_file(self) -> BoxCredentials:
        """Load Box credentials from a JSON file.

        Returns
        -------
        BoxCredentials
            Parsed credential payload from disk.

        Raises
        ------
        BoxAuthFileError
            Raised when the file is missing, unreadable, malformed,
            or missing required keys.
        """
        if not self._json_file:
            raise BoxAuthFileError("No Box credential file path was configured.")

        try:
            with self._json_file.open("r", encoding="utf-8") as file:
                payload = json.load(file)
        except FileNotFoundError as exc:
            raise BoxAuthFileError("Credential file not found.") from exc
        except json.JSONDecodeError as exc:
            raise BoxAuthFileError("Invalid JSON in credential file.") from exc
        except OSError as exc:
            raise BoxAuthFileError("Failed to read credential file.") from exc

        try:
            return BoxCredentials(
                client_id=payload["BOX_CLIENT_ID"],
                client_secret=payload["BOX_CLIENT_SECRET"],
                refresh_token=payload["refresh_token"],
                access_token=payload.get("access_token", ""),
                expires_at=int(payload.get("expires_at", 0)),
            )
        except KeyError as exc:
            raise BoxAuthFileError("Credential file is missing required keys.") from exc

    def _ensure_loaded(self) -> None:
        """Ensure credentials have been loaded into memory.

        Notes
        -----
        Environment variables are preferred. File-backed credentials are
        used only as a fallback for local development.
        """
        if self._credentials is not None:
            return

        self._credentials = self._load_from_env()
        if self._credentials is None:
            self._credentials = self._load_from_file()

    def _save_credentials(self) -> None:
        """Persist the latest credentials to disk when file-backed.

        Raises
        ------
        BoxAuthFileError
            Raised when updated credentials cannot be written.

        Notes
        -----
        When credentials originate from environment variables, no write
        occurs because the function filesystem should not be treated as
        durable secret storage.
        """
        if not self._json_file or self._credentials is None:
            return

        temp_file = self._json_file.with_suffix(self._json_file.suffix + ".tmp")
        payload = {
            "BOX_CLIENT_ID": self._credentials.client_id,
            "BOX_CLIENT_SECRET": self._credentials.client_secret,
            "refresh_token": self._credentials.refresh_token,
            "access_token": self._credentials.access_token,
            "expires_at": self._credentials.expires_at,
        }

        try:
            with temp_file.open("w", encoding="utf-8") as file:
                json.dump(payload, file, indent=2)
            os.replace(temp_file, self._json_file)
        except OSError as exc:
            raise BoxAuthFileError("Failed to save credentials.") from exc

    def _refresh_access_token(
        self,
        max_retries: int = 5,
        base_delay: float = 0.5,
        max_delay: float = 30.0,
    ) -> str:
        """Refresh the Box access token using the refresh token.

        Parameters
        ----------
        max_retries : int, optional
            Maximum number of transient retry attempts.
        base_delay : float, optional
            Starting delay in seconds for exponential backoff.
        max_delay : float, optional
            Upper bound for the retry delay in seconds.

        Returns
        -------
        str
            Newly issued Box access token.

        Raises
        ------
        BoxAuthTokenError
            Raised when token refresh fails permanently.
        """
        self._ensure_loaded()
        assert self._credentials is not None

        url = "https://api.box.com/oauth2/token"
        last_error: Exception | None = None

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.post(
                    url,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self._credentials.refresh_token,
                        "client_id": self._credentials.client_id,
                        "client_secret": self._credentials.client_secret,
                    },
                    timeout=10,
                )
            except requests.RequestException as exc:
                last_error = exc
                retryable = True
            else:
                if response.status_code == 200:
                    try:
                        data = response.json()
                        self._credentials.access_token = data["access_token"]
                        self._credentials.refresh_token = data["refresh_token"]
                        self._credentials.expires_at = int(time.time()) + int(data["expires_in"]) - 60
                        self._save_credentials()
                        return self._credentials.access_token
                    except KeyError as exc:
                        raise BoxAuthTokenError("Malformed token response.") from exc

                if response.status_code in (429, 500, 502, 503, 504):
                    last_error = BoxAuthTokenError(
                        f"Transient error refreshing token: {response.status_code} {response.text}"
                    )
                    retryable = True
                else:
                    raise BoxAuthTokenError(
                        f"Token refresh failed: {response.status_code} {response.text}"
                    )

            if attempt == max_retries or not retryable:
                break

            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            time.sleep(random.uniform(0, delay))

        raise BoxAuthTokenError(f"Token refresh failed after {max_retries} attempts.") from last_error

    def get_valid_access_token(self) -> str:
        """Return a valid Box access token.

        Returns
        -------
        str
            Active access token suitable for authenticated API calls.

        Notes
        -----
        A cached token is reused when it has not expired. Otherwise a
        token refresh is performed.
        """
        self._ensure_loaded()
        assert self._credentials is not None

        if self._credentials.access_token and time.time() < self._credentials.expires_at:
            return self._credentials.access_token

        return self._refresh_access_token()
