"""Tests for the Evernote-desktop-session token extractor."""

from __future__ import annotations

import base64
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from evernote_backup.cli_app_util import ProgramTerminatedError
from evernote_backup.desktop_session import (
    _decrypt_secure_blob,
    _default_config_dir,
    _get_os_key,
    _keyring_service_and_account,
    extract_token,
    list_desktop_users,
)

pytestmark = pytest.mark.skipif(
    sys.platform not in ("win32", "darwin"),
    reason="requires Windows or macOS (pycryptodome-dependent features)",
)


# ---- Fake desktop-session layout -------------------------------------------


class FakeDesktopSession:
    """Configurable fake of an Evernote desktop user-config directory.

    Mutate attributes, then call :meth:`write` to materialize (or refresh)
    the multi-user DB and encrypted secure-storage blob on disk. Same idea
    as :class:`TokenBundleMock` in conftest.
    """

    def __init__(self, tmp_path: Path) -> None:
        self.config_dir = tmp_path / "Evernote"

        self.user_id = "151636"
        self.username = "beernutz"
        self.email = "beernutz@gmail.com"

        self.s_token = "S=s3:U=25054:E=19f97d7cee2:C=19f9769f1e2:P=1dd:A=en-w32-xauth-new:V=2:H=deadbeef"
        self.shard = "s3"
        self.host = "www.evernote.com"
        self.jwt_access = "eyJhbGciOiJIUzI1NiJ9.fake.fake"
        self.jwt_refresh: str | None = None
        self.client_id: str | None = None

        self.aes_key = b"\x11" * 32

    # -- derived paths -------------------------------------------------------

    @property
    def multiuser_db_path(self) -> Path:
        return (
            self.config_dir
            / "conduit-storage"
            / "https%3A%2F%2Fwww.evernote.com"
            / "_ConduitMultiUserDB.sql"
        )

    @property
    def storage_path(self) -> Path:
        return self.config_dir / "secure-storage" / f"authtoken_user_{self.user_id}"

    # -- payload / crypto ----------------------------------------------------

    @property
    def userstore_payload(self) -> dict:
        """JSON dict Evernote stores (base64-encoded) inside the encrypted blob.

        Set any field to ``None`` to omit it from the payload (e.g. drop
        ``s_token`` to exercise the missing-token error path).
        """
        payload: dict = {}
        if self.s_token is not None:
            payload["t"] = self.s_token
        if self.shard is not None:
            payload["sh"] = self.shard
        if self.host is not None:
            payload["h"] = self.host
        if self.jwt_access is not None:
            payload["j"] = self.jwt_access
        if self.jwt_refresh is not None:
            payload["nrt"] = self.jwt_refresh
        if self.client_id is not None:
            payload["nci"] = self.client_id
        return payload

    def _encrypt_userstore(self) -> tuple[bytes, bytes]:
        from Crypto.Cipher import AES
        from Crypto.Util.Padding import pad

        plaintext = base64.b64encode(json.dumps(self.userstore_payload).encode("utf-8"))
        iv = b"\x33" * 16
        cipher = AES.new(self.aes_key, AES.MODE_CBC, iv)
        return cipher.encrypt(pad(plaintext, AES.block_size)), iv

    @property
    def keyring_secret(self) -> str:
        """Value that ``keyring.get_password`` should return for this AES key.

        On Windows Evernote stores the credential as raw ASCII bytes; keyring's
        WinVault backend decodes CredentialBlob as UTF-16, so get_password
        returns the misinterpreted string. Re-encoding with utf-16-le restores
        the original. On macOS the secret is a normal UTF-8 string.
        """
        raw = b"enote-encr-key" + base64.b64encode(self.aes_key)
        if sys.platform.startswith("win"):
            return raw.decode("utf-16")
        return raw.decode("utf-8")

    # -- materialize on disk -------------------------------------------------

    def write(self) -> Path:
        """Write multi-user DB + secure-storage blob; return config dir."""
        self.multiuser_db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(self.multiuser_db_path))
        try:
            con.execute("DROP TABLE IF EXISTS MultiUsers")
            con.execute("CREATE TABLE MultiUsers (Tkey TEXT, TValue TEXT)")
            con.execute(
                "INSERT INTO MultiUsers VALUES (?, ?)",
                (
                    f"User:{self.user_id}",
                    json.dumps({"username": self.username, "email": self.email}),
                ),
            )
            con.commit()
        finally:
            con.close()

        ciphertext, iv = self._encrypt_userstore()
        self.storage_path.parent.mkdir(parents=True, exist_ok=True)
        self.storage_path.write_text(
            json.dumps(
                {
                    "iv": base64.b64encode(iv).decode("ascii"),
                    # Evernote writes each raw byte as one ISO-8859-1 char.
                    "encrypted": ciphertext.decode("latin-1"),
                }
            ),
            encoding="utf-8",
        )
        return self.config_dir

    def patch_keyring(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Point ``keyring.get_password`` at this fake's AES key."""
        monkeypatch.setattr(
            "keyring.get_password",
            lambda service, account: self.keyring_secret,
        )


@pytest.fixture
def fake_desktop_session(tmp_path: Path) -> FakeDesktopSession:
    """Writable fake Evernote desktop config dir with one logged-in user."""
    fake = FakeDesktopSession(tmp_path)
    fake.write()
    return fake


# ---- list_desktop_users -----------------------------------------------------


def test_list_users_no_db(tmp_path):
    with pytest.raises(ProgramTerminatedError, match="not found"):
        list_desktop_users(tmp_path / "Evernote")


def test_list_users_returns_logged_in_user(fake_desktop_session):
    users = list_desktop_users(fake_desktop_session.config_dir)
    assert len(users) == 1
    u = users[0]
    assert u.user_id == fake_desktop_session.user_id
    assert u.username == fake_desktop_session.username
    assert u.email == fake_desktop_session.email
    # Secure-storage path is populated but token not yet decrypted
    assert u.s_token == ""
    assert u.storage_path == fake_desktop_session.storage_path


# ---- _decrypt_secure_blob ---------------------------------------------------


def test_decrypt_secure_blob_roundtrip(fake_desktop_session):
    data = _decrypt_secure_blob(
        fake_desktop_session.storage_path, fake_desktop_session.aes_key
    )
    assert data["t"] == fake_desktop_session.s_token
    assert data["sh"] == fake_desktop_session.shard
    assert data["h"] == fake_desktop_session.host
    assert data["j"] == fake_desktop_session.jwt_access


def test_decrypt_secure_blob_wrong_key_raises(fake_desktop_session):
    with pytest.raises(ProgramTerminatedError, match="PKCS7"):
        _decrypt_secure_blob(fake_desktop_session.storage_path, b"\x00" * 32)


def test_decrypt_secure_blob_wrong_key_length_raises(fake_desktop_session):
    with pytest.raises(ProgramTerminatedError, match="key length"):
        _decrypt_secure_blob(fake_desktop_session.storage_path, b"\x00" * 16)


# ---- OS key via keyring -----------------------------------------------------


def test_keyring_service_and_account_windows(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    service, account = _keyring_service_and_account("151636")
    assert account == "AuthToken:User:151636"
    assert service == "Evernote/AuthToken:User:151636"


def test_keyring_service_and_account_darwin(monkeypatch):
    monkeypatch.setattr("sys.platform", "darwin")
    service, account = _keyring_service_and_account("151636")
    assert account == "AuthToken:User:151636"
    assert service == "Evernote"


def test_get_os_key_roundtrip(fake_desktop_session, monkeypatch):
    fake_desktop_session.patch_keyring(monkeypatch)
    assert _get_os_key(fake_desktop_session.user_id) == fake_desktop_session.aes_key


def test_get_os_key_missing_raises(monkeypatch):
    monkeypatch.setattr("keyring.get_password", lambda service, account: None)
    with pytest.raises(ProgramTerminatedError, match="No Evernote encryption key"):
        _get_os_key("151636")


def test_get_os_key_locked_raises(monkeypatch):
    from keyring.errors import KeyringLocked

    def _raise(*_a, **_k):
        raise KeyringLocked("locked")

    monkeypatch.setattr("keyring.get_password", _raise)
    with pytest.raises(ProgramTerminatedError, match="locked"):
        _get_os_key("151636")


# ---- extract_token (with mocked OS key) -------------------------------------


def test_extract_token(fake_desktop_session, monkeypatch):
    """End-to-end extraction with a mocked keyring read."""
    fake_desktop_session.patch_keyring(monkeypatch)

    session = extract_token(
        user_id=fake_desktop_session.user_id,
        config_dir=fake_desktop_session.config_dir,
    )
    assert session.s_token == fake_desktop_session.s_token
    assert session.shard == fake_desktop_session.shard
    assert session.host == fake_desktop_session.host
    assert session.jwt_access == fake_desktop_session.jwt_access
    assert session.user_id == fake_desktop_session.user_id
    assert session.username == fake_desktop_session.username
    assert session.email == fake_desktop_session.email


def test_extract_token_custom_jwt(fake_desktop_session, monkeypatch):
    """Custom JWT / refresh / client_id flow through the encrypted blob."""
    fake_desktop_session.jwt_access = "eyJ.custom.access"
    fake_desktop_session.jwt_refresh = "eyJ.custom.refresh"
    fake_desktop_session.client_id = "custom-client-id"
    fake_desktop_session.write()
    fake_desktop_session.patch_keyring(monkeypatch)

    session = extract_token(
        user_id=fake_desktop_session.user_id,
        config_dir=fake_desktop_session.config_dir,
    )
    assert session.jwt_access == "eyJ.custom.access"
    assert session.jwt_refresh == "eyJ.custom.refresh"
    assert session.client_id == "custom-client-id"


def test_extract_token_no_token_field_raises(fake_desktop_session, monkeypatch):
    """If the decrypted blob has no 't' field, surface a clear error."""
    fake_desktop_session.s_token = None
    fake_desktop_session.write()
    fake_desktop_session.patch_keyring(monkeypatch)

    with pytest.raises(ProgramTerminatedError, match="no 't' \\(token\\) field"):
        extract_token(
            user_id=fake_desktop_session.user_id,
            config_dir=fake_desktop_session.config_dir,
        )


def test_extract_token_missing_user_raises(fake_desktop_session):
    with pytest.raises(ProgramTerminatedError, match="not found"):
        extract_token(user_id="999999", config_dir=fake_desktop_session.config_dir)


def test_extract_token_key_missing_raises(fake_desktop_session, monkeypatch):
    monkeypatch.setattr("keyring.get_password", lambda service, account: None)

    with pytest.raises(ProgramTerminatedError, match="No Evernote encryption key"):
        extract_token(
            user_id=fake_desktop_session.user_id,
            config_dir=fake_desktop_session.config_dir,
        )


# ---- _default_config_dir per platform --------------------------------------


def test_default_config_dir_windows(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\scott\AppData\Roaming")
    assert _default_config_dir() == Path(r"C:\Users\scott\AppData\Roaming\Evernote")


def test_default_config_dir_darwin(monkeypatch):
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(
        "pathlib.Path.home", lambda: Path("/Users/scott"), raising=False
    )
    assert _default_config_dir() == Path(
        "/Users/scott/Library/Application Support/Evernote"
    )
