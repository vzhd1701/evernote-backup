"""Extract the Evernote auth token from a logged-in Evernote desktop client.

The Evernote desktop client (Windows / macOS)
holds a valid token in the user's local profile - in an encrypted
blob in the Evernote user config directory.

Algorithm
---------
1. Locate the Evernote user config directory (per platform).
2. Open ``conduit-storage/.../_ConduitMultiUserDB.sql`` to enumerate the
   logged-in user(s).
3. For each user, locate ``secure-storage/authtoken_user_<userID>`` (a
   JSON file with ``{"iv": "<b64>", "encrypted": "<ISO-8859-1 binary>"}``).
4. Fetch the AES-256 key for that user from the OS secret store
   (Windows Credential Manager / macOS Keychain).
5. Decrypt with AES-256-CBC, strip PKCS7, base64-decode, parse the JSON
   user-store blob. Its ``t`` field is the classic ``S=...`` token.

If multiple users are present the caller can pick one by Evernote user
ID via :func:`extract_token` ``user_id=``; otherwise the first one is
returned.
"""

from __future__ import annotations

import base64
import json
import logging
import os
import sqlite3
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from evernote_backup.cli_app_util import ProgramTerminatedError

logger = logging.getLogger(__name__)

# key prefix as stored in the OS secret store (Windows CredMan blob and
# macOS Keychain password are both prefixed with this same string).
_KEY_PREFIX = "enote-encr-key"
_KEYRING_SERVICE = "Evernote"


@dataclass
class DesktopSession:
    """One logged-in Evernote user recovered from the desktop client."""

    user_id: str
    username: str
    email: str
    s_token: str
    shard: str
    host: str
    jwt_access: Optional[str] = None
    jwt_refresh: Optional[str] = None
    client_id: Optional[str] = None
    storage_path: Optional[Path] = None


# ---------------------------------------------------------------------------
# Platform-specific user-config-directory discovery + secure-storage read
# ---------------------------------------------------------------------------


def _default_config_dir() -> Path:
    """Best-effort location of the Evernote user config directory."""
    if sys.platform.startswith("win"):
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata) / "Evernote"
        return Path.home() / "Evernote"
    if sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Evernote"
    raise ProgramTerminatedError(
        f"Evernote desktop session extraction is only supported on Windows"
        f" and macOS (this platform is {sys.platform!r})."
    )


def _conduit_subdir(config_dir: Path) -> Path:
    """Path to the conduit-storage host subdirectory."""
    return config_dir / "conduit-storage" / "https%3A%2F%2Fwww.evernote.com"


def _multi_user_db(config_dir: Path) -> Path:
    return _conduit_subdir(config_dir) / "_ConduitMultiUserDB.sql"


def _secure_storage_dir(config_dir: Path) -> Path:
    return config_dir / "secure-storage"


def list_desktop_users(config_dir: Optional[Path] = None) -> List[DesktopSession]:
    """Enumerate the users currently logged in to the Evernote desktop client.

    Returns one :class:`DesktopSession` per user with ``s_token`` etc. left
    blank - call :func:`extract_token` (or just read ``s_token`` after
    picking) to actually decrypt each user's secure-storage blob.
    """
    config_dir = config_dir or _default_config_dir()
    db_path = _multi_user_db(config_dir)
    if not db_path.exists():
        raise ProgramTerminatedError(
            f"Evernote desktop user database not found at {db_path}."
            " Make sure the Evernote desktop app is installed and at least"
            " one user is logged in."
        )

    con = sqlite3.connect(str(db_path))
    try:
        cur = con.cursor()
        cur.execute("SELECT Tkey, TValue FROM MultiUsers")
        out: List[DesktopSession] = []
        for tkey, tvalue in cur.fetchall():
            try:
                data = json.loads(tvalue)
            except json.JSONDecodeError:
                continue
            user_id = tkey.split(":", 1)[1]
            out.append(
                DesktopSession(
                    user_id=user_id,
                    username=str(data.get("username", "?")),
                    email=str(data.get("email", "?")),
                    s_token="",
                    shard="",
                    host="",
                    storage_path=_secure_storage_dir(config_dir)
                    / f"authtoken_user_{user_id}",
                )
            )
    finally:
        con.close()
    return out


# ---------------------------------------------------------------------------
# OS secret-store reads via keyring (Windows CredMan / macOS Keychain)
# ---------------------------------------------------------------------------


def _keyring_service_and_account(user_id: str) -> tuple[str, str]:
    """Return ``(service, account)`` for Evernote's AES key in the OS store.

    Evernote (Electron + keytar) stores the key under account
    ``AuthToken:User:<id>``. On Windows the Credential Manager target name
    is ``Evernote/AuthToken:User:<id>`` (keyring service name); on macOS
    the Keychain service is just ``Evernote``.
    """
    account = f"AuthToken:User:{user_id}"
    if sys.platform.startswith("win"):
        return f"{_KEYRING_SERVICE}/{account}", account
    return _KEYRING_SERVICE, account


def _get_os_key(user_id: str) -> bytes:
    """Fetch the AES-256 key for *user_id* from the OS secret store."""
    try:
        import keyring
        from keyring.errors import KeyringError, KeyringLocked
    except ImportError as e:  # pragma: no cover
        raise ProgramTerminatedError(
            "Reading the Evernote auth key requires the 'keyring' package."
        ) from e

    service, account = _keyring_service_and_account(user_id)
    try:
        secret = keyring.get_password(service, account)
    except KeyringLocked as e:
        raise ProgramTerminatedError(
            "Could not access the system credential store (it is locked)."
            " Unlock it when prompted, or re-run with the desktop session"
            " unlocked."
        ) from e
    except KeyringError as e:
        raise ProgramTerminatedError(
            f"Could not read credential for user {user_id!r}"
            f" (service={service!r}): {e}."
            " Is the Evernote desktop client installed and logged in for"
            " the current user?"
        ) from e

    if not secret:
        raise ProgramTerminatedError(
            f"No Evernote encryption key found in the credential store for"
            f" user {user_id!r} (service={service!r}, account={account!r})."
            " Is the Evernote desktop client installed and logged in for"
            " the current user?"
        )

    # Evernote stores the secret as raw ASCII bytes
    # ("enote-encr-key" + base64(key)). keytar writes that as a UTF-8/ASCII
    # blob on Windows; keyring's WinVault backend decodes CredentialBlob as
    # UTF-16 first, which misinterprets the ASCII payload. Re-encoding with
    # utf-16-le restores the original bytes. On macOS the secret is already
    # a proper UTF-8 string.
    if sys.platform.startswith("win"):
        raw = secret.encode("utf-16-le")
    else:
        raw = secret.encode("utf-8")

    prefix = _KEY_PREFIX.encode("ascii")
    if not raw.startswith(prefix):
        raise ProgramTerminatedError(
            f"Credential for user {user_id!r} has unexpected prefix"
            f" {raw[: len(prefix)]!r}; cannot decrypt Evernote token."
        )
    return base64.b64decode(raw[len(prefix) :])


# ---------------------------------------------------------------------------
# AES-256-CBC decrypt of the secure-storage blob
# ---------------------------------------------------------------------------


def _decrypt_secure_blob(blob_path: Path, key: bytes) -> dict:
    """Decrypt ``authtoken_user_*`` and return the parsed user-store dict."""
    try:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import unpad
    except ImportError as e:  # pragma: no cover
        raise ProgramTerminatedError(
            "Decrypting the Evernote secure-storage blob requires the"
            " 'pycryptodome' package."
        ) from e

    if len(key) != 32:
        raise ProgramTerminatedError(
            f"Unexpected AES key length {len(key)} (need 32 for AES-256)."
        )

    blob = json.loads(blob_path.read_text(encoding="utf-8"))
    iv = base64.b64decode(blob["iv"])
    # Evernote writes each raw ciphertext byte as one ISO-8859-1 char in
    # the JSON "encrypted" field.
    ciphertext = blob["encrypted"].encode("latin-1")

    cipher = AES.new(key, AES.MODE_CBC, iv)
    try:
        plaintext = unpad(cipher.decrypt(ciphertext), AES.block_size)
    except ValueError as e:
        raise ProgramTerminatedError(
            f"Invalid PKCS7 padding in {blob_path.name}; key may be wrong."
        ) from e

    # Plaintext is a base64-encoded JSON blob describing the user store.
    userstore_b64 = plaintext.decode("utf-8")
    return json.loads(base64.b64decode(userstore_b64))


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------


def extract_token(
    user_id: Optional[str] = None,
    config_dir: Optional[Path] = None,
) -> DesktopSession:
    """Pull the ``S=...`` auth token out of the Evernote desktop client.

    Parameters
    ----------
    user_id
        If the desktop client has multiple logged-in users, pick the
        one with this Evernote user ID. Defaults to the only/first user.
    config_dir
        Override the Evernote user config directory (advanced).

    Raises :class:`ProgramTerminatedError` if the desktop client isn't
    installed, no user is logged in, or the secure storage can't be
    decrypted.
    """
    config_dir = config_dir or _default_config_dir()

    users = list_desktop_users(config_dir)
    if not users:
        raise ProgramTerminatedError("No logged-in Evernote desktop users were found.")

    if user_id is not None:
        chosen = next((u for u in users if u.user_id == user_id), None)
        if chosen is None:
            avail = ", ".join(u.user_id for u in users)
            raise ProgramTerminatedError(
                f"Requested desktop user {user_id!r} not found; available: {avail}."
            )
    elif len(users) == 1:
        chosen = users[0]
    else:
        chosen = users[0]
        avail = ", ".join(f"{u.user_id} ({u.email})" for u in users)
        logger.warning(
            "Multiple Evernote desktop users found (%s);"
            " automatically selected first user %s (%s)."
            " Pass ID with --oauth-en-user to choose a specific user.",
            avail,
            chosen.user_id,
            chosen.email,
        )

    if chosen.storage_path is None or not chosen.storage_path.exists():
        raise ProgramTerminatedError(
            f"Secure-storage file for user {chosen.user_id!r} not found at"
            f" {chosen.storage_path}."
        )

    key = _get_os_key(chosen.user_id)
    data = _decrypt_secure_blob(chosen.storage_path, key)

    chosen.s_token = str(data.get("t", "") or "")
    chosen.shard = str(data.get("sh", "") or "")
    chosen.host = str(data.get("h", "") or "")
    chosen.jwt_access = data.get("j") or None
    chosen.jwt_refresh = data.get("nrt") or None
    chosen.client_id = data.get("nci") or None

    if not chosen.s_token:
        raise ProgramTerminatedError(
            f"Decrypted secure storage for user {chosen.user_id!r}"
            " but found no 't' (token) field. The Evernote desktop client"
            " may need to log in again."
        )

    return chosen
