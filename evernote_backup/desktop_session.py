"""Extract the Evernote auth token from a logged-in Evernote desktop client.

When the legacy Evernote OAuth 1.0a endpoint at www.evernote.com/oauth was
retired by Bending Spoons (who acquired Evernote in 2023), there is no
longer a way for ``evernote-backup init-db`` to obtain a fresh ``S=...``
token on its own. The new Evernote desktop client (Windows / macOS)
still holds a valid token in the user's local profile - in an encrypted
blob in the Evernote user config directory.

This module ports the algorithm used by vzhd1701/evertoken (Go) into
Python so ``evernote-backup`` can recover the token automatically when
``--from-desktop-session`` is passed.

Algorithm
---------
1. Locate the Evernote user config directory (per platform).
2. Open ``conduit-storage/.../_ConduitMultiUserDB.sql`` to enumerate the
   logged-in user(s).
3. For each user, locate ``secure-storage/authtoken_user_<userID>`` (a
   JSON file with ``{"iv": "<b64>", "encrypted": "<ISO-8859-1 binary>"}``).
4. Fetch the AES-256 key for that user from the OS secret store
   (Windows Credential Manager / macOS Keychain / Linux libsecret).
5. Decrypt with AES-256-CBC, strip PKCS7, base64-decode, parse the JSON
   user-store blob. Its ``t`` field is the classic ``S=...`` token.

If multiple users are present the caller can pick one by Evernote user
ID via :func:`extract_token` ``user_id=``; otherwise the first one is
returned.
"""
from __future__ import annotations

import base64
import json
import os
import shutil
import sqlite3
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional

from evernote_backup.cli_app_util import ProgramTerminatedError

# key prefix as stored in the OS secret store (Windows CredMan blob and
# macOS Keychain password are both prefixed with this same string).
_KEY_PREFIX = "enote-encr-key"


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
    elif sys.platform == "darwin":
        return Path.home() / "Library" / "Application Support" / "Evernote"
    else:
        xdg = os.environ.get("XDG_CONFIG_HOME")
        if xdg:
            return Path(xdg) / "Evernote"
        return Path.home() / ".config" / "Evernote"
    return Path.home() / "Evernote"


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
# OS secret-store reads (per platform)
# ---------------------------------------------------------------------------


def _get_key_windows(target: str) -> bytes:
    """Read a generic credential from Windows Credential Manager."""
    try:
        import win32cred  # type: ignore
    except ImportError as e:  # pragma: no cover
        raise ProgramTerminatedError(
            "Reading the Evernote auth key on Windows requires the"
            " 'pywin32' package. Install it with:"
            " `pip install pywin32`."
        ) from e

    try:
        cred = win32cred.CredRead(target, win32cred.CRED_TYPE_GENERIC, 0)
    except Exception as e:  # noqa: BLE001
        raise ProgramTerminatedError(
            f"Could not read Windows credential '{target}': {e}."
            " Is the Evernote desktop client installed and logged in for"
            " the current user?"
        ) from e

    blob = cred["CredentialBlob"]
    if not isinstance(blob, bytes):
        blob = blob.encode("utf-16-le")
    if not blob.startswith(_KEY_PREFIX.encode("ascii")):
        raise ProgramTerminatedError(
            f"Windows credential '{target}' has unexpected prefix"
            f" {blob[:len(_KEY_PREFIX)]!r}; cannot decrypt Evernote token."
        )
    return base64.b64decode(blob[len(_KEY_PREFIX):])


def _get_key_macos(target: str) -> bytes:
    """Read a generic password item from the macOS Keychain."""
    if not shutil.which("/usr/bin/security"):
        raise ProgramTerminatedError(
            "/usr/bin/security not found; cannot read macOS Keychain."
        )
    try:
        out = subprocess.run(
            [
                "/usr/bin/security",
                "find-generic-password",
                "-s", target.split("/", 1)[0],
                "-wa", target,
            ],
            check=True,
            capture_output=True,
            timeout=10,
        )
    except subprocess.CalledProcessError as e:
        stderr = (e.stderr or b"").decode("utf-8", "replace").strip()
        raise ProgramTerminatedError(
            f"Could not read macOS Keychain entry '{target}': {stderr}."
            " Is the Evernote desktop client installed and logged in for"
            " the current user?"
        ) from e
    data = out.stdout.strip()
    if data.startswith(_KEY_PREFIX.encode("ascii")):
        data = data[len(_KEY_PREFIX):]
    return base64.b64decode(data)


def _get_key_linux(target: str) -> bytes:
    """Read a secret from libsecret via the ``secret-tool`` CLI."""
    if not shutil.which("secret-tool"):
        raise ProgramTerminatedError(
            "The 'secret-tool' CLI is required to read the Evernote"
            " key from libsecret on Linux. Install it (e.g. via"
            " libsecret-tools) and make sure a Secret Service provider"
            " such as GNOME Keyring or KWallet is running for the"
            " current user."
        )
    service = target.split("/", 1)[0]
    account = target[len(service) + 1 :] if "/" in target else ""
    try:
        out = subprocess.run(
            [
                "secret-tool",
                "lookup",
                "service", service,
                "account", account,
            ],
            check=True,
            capture_output=True,
            timeout=10,
        )
    except subprocess.CalledProcessError as e:
        raise ProgramTerminatedError(
            f"Could not read libsecret entry service={service}"
            f" account={account}: {e}."
        ) from e
    data = out.stdout.strip()
    if data.startswith(_KEY_PREFIX.encode("ascii")):
        data = data[len(_KEY_PREFIX):]
    return base64.b64decode(data)


def _get_os_key(target: str) -> bytes:
    if sys.platform.startswith("win"):
        return _get_key_windows(target)
    if sys.platform == "darwin":
        return _get_key_macos(target)
    return _get_key_linux(target)


# ---------------------------------------------------------------------------
# AES-256-CBC decrypt of the secure-storage blob
# ---------------------------------------------------------------------------


def _decrypt_secure_blob(blob_path: Path, key: bytes) -> dict:
    """Decrypt ``authtoken_user_*`` and return the parsed user-store dict."""
    try:
        from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
        from cryptography.hazmat.backends import default_backend
    except ImportError as e:  # pragma: no cover
        raise ProgramTerminatedError(
            "Decrypting the Evernote secure-storage blob requires the"
            " 'cryptography' package. Install it with:"
            " `pip install cryptography`."
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

    cipher = Cipher(algorithms.AES(key), modes.CBC(iv), backend=default_backend())
    dec = cipher.decryptor()
    padded = dec.update(ciphertext) + dec.finalize()
    pad = padded[-1]
    if not (0 < pad <= 16) or any(b != pad for b in padded[-pad:]):
        raise ProgramTerminatedError(
            f"Invalid PKCS7 padding in {blob_path.name}; key may be wrong."
        )
    plaintext = padded[: len(padded) - pad]

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
        raise ProgramTerminatedError(
            "No logged-in Evernote desktop users were found."
        )

    if user_id is not None:
        chosen = next((u for u in users if u.user_id == user_id), None)
        if chosen is None:
            avail = ", ".join(u.user_id for u in users)
            raise ProgramTerminatedError(
                f"Requested desktop user {user_id!r} not found;"
                f" available: {avail}."
            )
    elif len(users) == 1:
        chosen = users[0]
    else:
        # Multiple users - take the first one and warn via logger? The CLI
        # is expected to enumerate them for the user via --list.
        chosen = users[0]

    if chosen.storage_path is None or not chosen.storage_path.exists():
        raise ProgramTerminatedError(
            f"Secure-storage file for user {chosen.user_id!r} not found at"
            f" {chosen.storage_path}."
        )

    key = _get_os_key(f"Evernote/AuthToken:User:{chosen.user_id}")
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
