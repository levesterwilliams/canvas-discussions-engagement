# box_auth.py
# Author: Levester Williams
# Date: 16 Mar 2026

"""Box authentication helpers for Azure Functions and local execution.

This module supports two credential storage modes:

- Azure Key Vault for production-ready rotating OAuth state
- local JSON file fallback for development scenarios
"""

from __future__ import annotations

import json
import os
import random
import time
from dataclasses import dataclass
from pathlib import Path

import requests
from azure.core.exceptions import ResourceNotFoundError
from azure.identity import DefaultAzureCredential
from azure.keyvault.secrets import SecretClient


class BoxAuthError(Exception):
    """Base exception for Box authentication errors."""


class BoxAuthFileError(BoxAuthError):
    """Raised when credential file operations fail."""


class BoxAuthSecretStoreError(BoxAuthError):
    """Raised when secret store operations fail."""


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


class KeyVaultBoxSecretStore:
    """Read and write Box OAuth secrets in Azure Key Vault.

    Parameters
    ----------
    vault_name : str or None, optional
        Name of the Azure Key Vault. When omitted, the value is loaded
        from the ``KEY_VAULT_NAME`` environment variable.

    Notes
    -----
    This store is intended for Azure Functions production deployments,
    where the function's managed identity can read and write secrets.
    """

    def __init__(self, vault_name: str | None = None) -> None:
        """Initialize the Key Vault secret client.

        Parameters
        ----------
        vault_name : str or None, optional
            Explicit Key Vault name override.

        Raises
        ------
        BoxAuthSecretStoreError
            Raised when no vault name is available.
        """
        resolved_vault_name = vault_name or os.getenv("KEY_VAULT_NAME")
        if not resolved_vault_name:
            raise BoxAuthSecretStoreError(
                "KEY_VAULT_NAME is required to use Azure Key Vault for Box credentials."
            )

        vault_url = f"https://{resolved_vault_name}.vault.azure.net"
        self._client = SecretClient(vault_url=vault_url, credential=DefaultAzureCredential())

    def _get_required_secret(self, secret_name: str) -> str:
        """Read a required secret value from Key Vault.

        Parameters
        ----------
        secret_name : str
            Name of the Key Vault secret.

        Returns
        -------
        str
            Secret value.

        Raises
        ------
        BoxAuthSecretStoreError
            Raised when the secret cannot be found or read.
        """
        try:
            return self._client.get_secret(secret_name).value
        except Exception as exc:
            raise BoxAuthSecretStoreError(f"Failed to read required secret '{secret_name}'.") from exc

    def _get_optional_secret(self, secret_name: str, default: str = "") -> str:
        """Read an optional secret value from Key Vault.

        Parameters
        ----------
        secret_name : str
            Name of the Key Vault secret.
        default : str, optional
            Fallback value returned when the secret does not exist.

        Returns
        -------
        str
            Secret value or the provided default.
        """
        try:
            return self._client.get_secret(secret_name).value
        except ResourceNotFoundError:
            return default
        except Exception as exc:
            raise BoxAuthSecretStoreError(f"Failed to read optional secret '{secret_name}'.") from exc

    def load(self) -> BoxCredentials:
        """Load Box OAuth state from Azure Key Vault.

        Returns
        -------
        BoxCredentials
            Credentials and cached token state loaded from Key Vault.
        """
        expires_at_raw = self._get_optional_secret("box-expires-at", "0")
        try:
            expires_at = int(expires_at_raw)
        except ValueError:
            expires_at = 0

        return BoxCredentials(
            client_id=self._get_required_secret("box-client-id"),
            client_secret=self._get_required_secret("box-client-secret"),
            refresh_token=self._get_required_secret("box-refresh-token"),
            access_token=self._get_optional_secret("box-access-token", ""),
            expires_at=expires_at,
        )

    def save_token_state(self, credentials: BoxCredentials) -> None:
        """Persist refreshed Box token state back to Key Vault.

        Parameters
        ----------
        credentials : BoxCredentials
            Updated credential object containing the latest access token,
            refresh token, and expiry time.

        Raises
        ------
        BoxAuthSecretStoreError
            Raised when the updated secrets cannot be persisted.
        """
        try:
            self._client.set_secret("box-refresh-token", credentials.refresh_token)
            self._client.set_secret("box-access-token", credentials.access_token)
            self._client.set_secret("box-expires-at", str(credentials.expires_at))
        except Exception as exc:
            raise BoxAuthSecretStoreError("Failed to persist refreshed Box token state to Key Vault.") from exc


class FileBoxSecretStore:
    """Read and write Box OAuth credentials from a local JSON file.

    Parameters
    ----------
    json_file : str or pathlib.Path
        Path to the local credential file.

    Notes
    -----
    This store exists as a local-development fallback. It should not be
    treated as the durable production secret store for Azure Functions.
    """

    def __init__(self, json_file: str | Path) -> None:
        """Initialize the file-backed secret store.

        Parameters
        ----------
        json_file : str or pathlib.Path
            Path to the credential JSON file.
        """
        self._json_file = Path(json_file)

    def load(self) -> BoxCredentials:
        """Load Box OAuth credentials from disk.

        Returns
        -------
        BoxCredentials
            Credentials parsed from the JSON payload.

        Raises
        ------
        BoxAuthFileError
            Raised when the file is unreadable, malformed, or missing
            required keys.
        """
        try:
            with self._json_file.open("r", encoding="utf-8") as file_handle:
                payload = json.load(file_handle)
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

    def save_token_state(self, credentials: BoxCredentials) -> None:
        """Persist refreshed Box token state to disk.

        Parameters
        ----------
        credentials : BoxCredentials
            Updated credential object containing the latest access token,
            refresh token, and expiry time.

        Raises
        ------
        BoxAuthFileError
            Raised when the updated credential payload cannot be written.
        """
        temp_file = self._json_file.with_suffix(self._json_file.suffix + ".tmp")
        payload = {
            "BOX_CLIENT_ID": credentials.client_id,
            "BOX_CLIENT_SECRET": credentials.client_secret,
            "refresh_token": credentials.refresh_token,
            "access_token": credentials.access_token,
            "expires_at": credentials.expires_at,
        }

        try:
            with temp_file.open("w", encoding="utf-8") as file_handle:
                json.dump(payload, file_handle, indent=2)
            os.replace(temp_file, self._json_file)
        except OSError as exc:
            raise BoxAuthFileError("Failed to save credentials.") from exc


class BoxAuthManager:
    """Acquire and refresh Box OAuth access tokens.

    Parameters
    ----------
    json_file : str or None, optional
        Path to a local JSON credential file used as a fallback when
        Azure Key Vault is not configured.
    vault_name : str or None, optional
        Explicit Key Vault name override. When omitted, the value is
        loaded from ``KEY_VAULT_NAME``.

    Notes
    -----
    The manager prefers Azure Key Vault so refreshed Box OAuth tokens
    can be durably persisted between Azure Function executions.
    """

    def __init__(self, json_file: str | None = None, vault_name: str | None = None) -> None:
        """Initialize the authentication manager.

        Parameters
        ----------
        json_file : str or None, optional
            Local credential file path for development fallback.
        vault_name : str or None, optional
            Explicit Key Vault name override.
        """
        self._json_file = Path(json_file) if json_file else None
        self._vault_name = vault_name
        self._secret_store: KeyVaultBoxSecretStore | FileBoxSecretStore | None = None
        self._credentials: BoxCredentials | None = None

    def _build_secret_store(self) -> KeyVaultBoxSecretStore | FileBoxSecretStore:
        """Create the preferred secret store implementation.

        Returns
        -------
        KeyVaultBoxSecretStore or FileBoxSecretStore
            Secret store instance used for loading and saving Box OAuth
            state.

        Raises
        ------
        BoxAuthError
            Raised when neither Azure Key Vault nor a local credential
            file is configured.
        """
        if self._vault_name or os.getenv("KEY_VAULT_NAME"):
            return KeyVaultBoxSecretStore(vault_name=self._vault_name)

        if self._json_file is not None:
            return FileBoxSecretStore(self._json_file)

        raise BoxAuthError(
            "No Box secret store is configured. Set KEY_VAULT_NAME or provide a local credential file."
        )

    def _ensure_loaded(self) -> None:
        """Ensure credentials have been loaded into memory.

        Notes
        -----
        The first call selects the secret store, loads credentials, and
        caches them for the lifetime of the current execution.
        """
        if self._credentials is not None and self._secret_store is not None:
            return

        self._secret_store = self._build_secret_store()
        self._credentials = self._secret_store.load()

    def _persist_token_state(self) -> None:
        """Persist the current Box token state through the active secret store.

        Raises
        ------
        BoxAuthError
            Raised when credentials have not been loaded or persistence
            fails.
        """
        if self._secret_store is None or self._credentials is None:
            raise BoxAuthError("Credentials must be loaded before token state can be persisted.")

        self._secret_store.save_token_state(self._credentials)

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
                        self._persist_token_state()
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
        token refresh is performed and the updated OAuth state is saved
        back to the configured secret store.
        """
        self._ensure_loaded()
        assert self._credentials is not None

        if self._credentials.access_token and time.time() < self._credentials.expires_at:
            return self._credentials.access_token

        return self._refresh_access_token()

