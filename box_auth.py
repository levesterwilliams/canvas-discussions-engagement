# box_auth.py
# Author: Levester Williams
# Date: 16 Mar 2026
#
# Script to gain access to BOX API


import json
import os
import time
import random
import requests

# =========================
# Exceptions
# =========================

class BoxAuthError(Exception):
    """Base exception for Box authentication errors."""
    pass


class BoxAuthFileError(BoxAuthError):
    """Raised when credential file operations fail."""
    pass


class BoxAuthTokenError(BoxAuthError):
    """Raised when token refresh fails."""
    pass

# =========================
# Manager
# =========================

class BoxAuthManager:
    def __init__(self, json_file: str):
        """
        Initialize the BoxAuthManager.

        Parameters
        ----------
        json_file : str
            Path to credential JSON file.
        """
        self._credentials = None
        self._json_file = json_file

    def load_json_file(self, json_file: str) -> dict:
        """
        Load credentials from disk.

        Parameters
        ----------
        json_file : str
            Path to JSON credential file.

        Returns
        -------
        dict
            Credential dictionary.

        Raises
        ------
        BoxAuthFileError
        """
        try:
            with open(json_file, 'r') as file:
                self._credentials = json.load(file)
                return self._credentials
        except FileNotFoundError as e:
            raise BoxAuthFileError("Credential file not found.") from e
        except json.JSONDecodeError as e:
            raise BoxAuthFileError("Invalid JSON in credential file.") from e
        except Exception as e:
            raise BoxAuthFileError("Failed to load credentials.") from e

    def _ensure_loaded(self):
        """Ensure credentials are loaded correctly"""
        if self._credentials is None:
            self.load_json_file(self._json_file)

    def _save_credentials(self):
        """Atomically persist credentials to disk."""
        temp_file = self._json_file + ".tmp"

        try:
            with open(temp_file, "w") as f:
                json.dump(self._credentials, f, indent=2)

            os.replace(temp_file, self._json_file)
        except Exception as e:
            raise BoxAuthFileError("Failed to save credentials.") from e

    def _refresh_access_token(self,
                              max_retries: int = 5,
                              base_delay: float = 0.5,
                              max_delay: float = 30.0):
        """
        Refresh the Box access token using exponential backoff.

        Parameters
        ----------
        max_retries : int
            Maximum retry attempts.
        base_delay : float
            Initial delay (seconds).
        max_delay : float
            Maximum delay cap (seconds).

        Returns
        -------
        str
            New access token.

        Raises
        ------
        BoxAuthTokenError
        """
        self._ensure_loaded()

        url = "https://api.box.com/oauth2/token"

        for attempt in range(1, max_retries + 1):
            try:
                response = requests.post(
                    url,
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self._credentials["refresh_token"],
                        "client_id": self._credentials["BOX_CLIENT_ID"],
                        "client_secret": self._credentials["BOX_CLIENT_SECRET"]
                    },
                    timeout=10
                )
            except requests.RequestException as e:
                retryable = True
                error = e
            else:
                # Success
                if response.status_code == 200:
                    try:
                        data = response.json()

                        self._credentials["access_token"] = data["access_token"]
                        self._credentials["refresh_token"] = data["refresh_token"]
                        self._credentials["expires_at"] = (
                            int(time.time()) + data["expires_in"] - 60
                        )

                        self._save_credentials()
                        return self._credentials["access_token"]

                    except KeyError as e:
                        raise BoxAuthTokenError(
                            "Malformed token response."
                        ) from e

                # Retry only transient errors
                elif response.status_code in (429, 500, 502, 503, 504):
                    retryable = True
                    error = BoxAuthTokenError(
                        f"Transient error: {response.status_code} {response.text}"
                    )
                else:
                    # Non-retryable
                    raise BoxAuthTokenError(
                        f"Token refresh failed: {response.status_code} {response.text}"
                    )

            # Handle retry
            if attempt == max_retries or not retryable:
                raise BoxAuthTokenError(
                    f"Token refresh failed after {attempt} attempts."
                ) from error

            # Exponential backoff with jitter
            delay = min(max_delay, base_delay * (2 ** (attempt - 1)))
            jitter = random.uniform(0, delay)
            sleep_time = jitter

            time.sleep(sleep_time)

    def get_valid_access_token(self):
        """
        Get a valid access token, refreshing if necessary.

        Returns
        -------
        str
            Valid access token.

        Raises
        ------
        BoxAuthError
        """
        try:
            self._ensure_loaded()

            if time.time() < self._credentials.get("expires_at", 0):
                return self._credentials["access_token"]

            return self._refresh_access_token()

        except BoxAuthError:
            raise
        except Exception as e:
            raise BoxAuthError("Failed to obtain valid access token.") from e