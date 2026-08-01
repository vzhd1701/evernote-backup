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
        return self.keyring_secret_for_platform(sys.platform)

    def keyring_secret_for_platform(self, platform: str) -> str:
        raw = b"enote-encr-key" + base64.b64encode(self.aes_key)
        if platform.startswith("win"):
            return raw.decode("utf-16")
        return raw.decode("utf-8")

    # -- materialize on disk -------------------------------------------------

    def _ensure_db(self, *, clear: bool) -> sqlite3.Connection:
        self.multiuser_db_path.parent.mkdir(parents=True, exist_ok=True)
        con = sqlite3.connect(str(self.multiuser_db_path))
        if clear:
            con.execute("DROP TABLE IF EXISTS MultiUsers")
            con.execute("CREATE TABLE MultiUsers (Tkey TEXT, TValue TEXT)")
        return con

    def write(
        self,
        *,
        clear_db: bool = True,
        write_storage: bool = True,
        db_row: dict | None = None,
    ) -> Path:
        """Write multi-user DB row + secure-storage blob; return config dir.

        Parameters
        ----------
        clear_db
            When True (default), recreate MultiUsers from scratch. Set False
            to append another user into an existing DB (multi-user tests).
        write_storage
            When False, only update the multi-user DB (missing-blob tests).
        db_row
            Override the JSON stored in MultiUsers.TValue (missing username
            / email / invalid-json tests). Defaults to username+email.
        """
        con = self._ensure_db(clear=clear_db)
        try:
            if db_row is None:
                db_row = {"username": self.username, "email": self.email}
            con.execute(
                "INSERT INTO MultiUsers VALUES (?, ?)",
                (f"User:{self.user_id}", json.dumps(db_row)),
            )
            con.commit()
        finally:
            con.close()

        if write_storage:
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

    def write_empty_db(self) -> Path:
        """Create an empty MultiUsers table (no logged-in users)."""
        con = self._ensure_db(clear=True)
        con.commit()
        con.close()
        return self.config_dir

    def write_raw_db_row(self, tkey: str, tvalue: str, *, clear: bool = False) -> None:
        """Insert a raw MultiUsers row (invalid JSON / odd keys)."""
        con = self._ensure_db(clear=clear)
        try:
            con.execute("INSERT INTO MultiUsers VALUES (?, ?)", (tkey, tvalue))
            con.commit()
        finally:
            con.close()

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


# ---- _default_config_dir ----------------------------------------------------


def test_default_config_dir_windows(monkeypatch):
    # Build expected with Path / so separators match the host platform
    # (posix Path uses / even when the base string looks like a Windows path).
    appdata = r"C:\Users\scott\AppData\Roaming"
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("APPDATA", appdata)
    assert _default_config_dir() == Path(appdata) / "Evernote"


def test_default_config_dir_windows_no_appdata(monkeypatch):
    """Without APPDATA, Windows falls through to ~/Evernote."""
    home = Path(r"C:\Users\scott")
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr("pathlib.Path.home", lambda: home, raising=False)
    assert _default_config_dir() == home / "Evernote"


def test_default_config_dir_darwin(monkeypatch):
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr(
        "pathlib.Path.home", lambda: Path("/Users/scott"), raising=False
    )
    assert _default_config_dir() == Path(
        "/Users/scott/Library/Application Support/Evernote"
    )


def test_default_config_dir_unsupported_platform_raises(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    with pytest.raises(ProgramTerminatedError, match="only supported on Windows"):
        _default_config_dir()


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


def test_list_users_skips_invalid_json_rows(fake_desktop_session):
    """Corrupt MultiUsers rows are skipped; valid users still returned."""
    fake_desktop_session.write_raw_db_row("User:bad", "not-json{", clear=False)
    users = list_desktop_users(fake_desktop_session.config_dir)
    assert len(users) == 1
    assert users[0].user_id == fake_desktop_session.user_id


def test_list_users_missing_username_email_defaults(tmp_path):
    """Missing username/email fields fall back to '?'."""
    fake = FakeDesktopSession(tmp_path)
    fake.write(db_row={})
    users = list_desktop_users(fake.config_dir)
    assert len(users) == 1
    assert users[0].username == "?"
    assert users[0].email == "?"


def test_list_users_multiple(tmp_path):
    u1 = FakeDesktopSession(tmp_path)
    u1.user_id = "111"
    u1.username = "alice"
    u1.email = "alice@example.com"
    u1.write()

    u2 = FakeDesktopSession(tmp_path)
    u2.user_id = "222"
    u2.username = "bob"
    u2.email = "bob@example.com"
    u2.write(clear_db=False)

    users = list_desktop_users(u1.config_dir)
    assert [u.user_id for u in users] == ["111", "222"]
    assert users[0].username == "alice"
    assert users[1].username == "bob"


def test_list_users_empty_db(tmp_path):
    fake = FakeDesktopSession(tmp_path)
    fake.write_empty_db()
    assert list_desktop_users(fake.config_dir) == []


def test_list_users_uses_default_config_dir(tmp_path, monkeypatch):
    fake = FakeDesktopSession(tmp_path)
    fake.write()
    monkeypatch.setattr(
        "evernote_backup.desktop_session._default_config_dir",
        lambda: fake.config_dir,
    )
    users = list_desktop_users()
    assert len(users) == 1
    assert users[0].user_id == fake.user_id


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


def test_get_os_key_roundtrip_windows(fake_desktop_session, monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    secret = fake_desktop_session.keyring_secret_for_platform("win32")
    monkeypatch.setattr("keyring.get_password", lambda service, account: secret)
    assert _get_os_key(fake_desktop_session.user_id) == fake_desktop_session.aes_key


def test_get_os_key_roundtrip_darwin(fake_desktop_session, monkeypatch):
    monkeypatch.setattr("sys.platform", "darwin")
    secret = fake_desktop_session.keyring_secret_for_platform("darwin")
    monkeypatch.setattr("keyring.get_password", lambda service, account: secret)
    assert _get_os_key(fake_desktop_session.user_id) == fake_desktop_session.aes_key


def test_get_os_key_missing_raises(monkeypatch):
    monkeypatch.setattr("keyring.get_password", lambda service, account: None)
    with pytest.raises(ProgramTerminatedError, match="No Evernote encryption key"):
        _get_os_key("151636")


def test_get_os_key_empty_secret_raises(monkeypatch):
    monkeypatch.setattr("keyring.get_password", lambda service, account: "")
    with pytest.raises(ProgramTerminatedError, match="No Evernote encryption key"):
        _get_os_key("151636")


def test_get_os_key_locked_raises(monkeypatch):
    from keyring.errors import KeyringLocked

    def _raise(*_a, **_k):
        raise KeyringLocked("locked")

    monkeypatch.setattr("keyring.get_password", _raise)
    with pytest.raises(ProgramTerminatedError, match="locked"):
        _get_os_key("151636")


def test_get_os_key_keyring_error_raises(monkeypatch):
    from keyring.errors import KeyringError

    def _raise(*_a, **_k):
        raise KeyringError("backend boom")

    monkeypatch.setattr("keyring.get_password", _raise)
    with pytest.raises(ProgramTerminatedError, match="Could not read credential"):
        _get_os_key("151636")


def test_get_os_key_unexpected_prefix_raises(monkeypatch):
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.setattr(
        "keyring.get_password",
        lambda service, account: "wrong-prefix"
        + base64.b64encode(b"\x11" * 32).decode(),
    )
    with pytest.raises(ProgramTerminatedError, match="unexpected prefix"):
        _get_os_key("151636")


# ---- extract_token ----------------------------------------------------------


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


def test_extract_token_without_user_id_single_user(fake_desktop_session, monkeypatch):
    """With one user, user_id is optional and that user is chosen."""
    fake_desktop_session.patch_keyring(monkeypatch)
    session = extract_token(config_dir=fake_desktop_session.config_dir)
    assert session.user_id == fake_desktop_session.user_id
    assert session.s_token == fake_desktop_session.s_token


def test_extract_token_multiple_users_picks_first(tmp_path, monkeypatch, caplog):
    """With multiple users and no user_id, the first DB row is used."""
    u1 = FakeDesktopSession(tmp_path)
    u1.user_id = "111"
    u1.email = "one@example.com"
    u1.s_token = "S=s1:U=111:token1"
    u1.write()

    u2 = FakeDesktopSession(tmp_path)
    u2.user_id = "222"
    u2.email = "two@example.com"
    u2.s_token = "S=s1:U=222:token2"
    u2.aes_key = u1.aes_key
    u2.write(clear_db=False)

    u1.patch_keyring(monkeypatch)
    with caplog.at_level("WARNING", logger="evernote_backup.desktop_session"):
        session = extract_token(config_dir=u1.config_dir)
    assert session.user_id == "111"
    assert session.s_token == "S=s1:U=111:token1"
    assert "automatically selected first user 111 (one@example.com)" in caplog.text
    assert "111 (one@example.com), 222 (two@example.com)" in caplog.text


def test_extract_token_multiple_users_picks_requested(tmp_path, monkeypatch):
    u1 = FakeDesktopSession(tmp_path)
    u1.user_id = "111"
    u1.s_token = "S=s1:U=111:token1"
    u1.write()

    u2 = FakeDesktopSession(tmp_path)
    u2.user_id = "222"
    u2.s_token = "S=s1:U=222:token2"
    u2.aes_key = u1.aes_key
    u2.write(clear_db=False)

    u1.patch_keyring(monkeypatch)
    session = extract_token(user_id="222", config_dir=u1.config_dir)
    assert session.user_id == "222"
    assert session.s_token == "S=s1:U=222:token2"


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


def test_extract_token_nullish_optional_fields(fake_desktop_session, monkeypatch):
    """Empty/null optional JWT fields normalize to None; missing sh/h to ''."""
    fake_desktop_session.jwt_access = None
    fake_desktop_session.jwt_refresh = None
    fake_desktop_session.client_id = None
    fake_desktop_session.shard = None
    fake_desktop_session.host = None
    fake_desktop_session.write()
    fake_desktop_session.patch_keyring(monkeypatch)

    session = extract_token(
        user_id=fake_desktop_session.user_id,
        config_dir=fake_desktop_session.config_dir,
    )
    assert session.s_token == fake_desktop_session.s_token
    assert session.shard == ""
    assert session.host == ""
    assert session.jwt_access is None
    assert session.jwt_refresh is None
    assert session.client_id is None


def test_extract_token_empty_token_string_raises(fake_desktop_session, monkeypatch):
    """Explicit empty 't' is treated as missing."""
    fake_desktop_session.s_token = ""
    fake_desktop_session.write()
    fake_desktop_session.patch_keyring(monkeypatch)

    with pytest.raises(ProgramTerminatedError, match="no 't' \\(token\\) field"):
        extract_token(
            user_id=fake_desktop_session.user_id,
            config_dir=fake_desktop_session.config_dir,
        )


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


def test_extract_token_no_users_raises(tmp_path):
    fake = FakeDesktopSession(tmp_path)
    fake.write_empty_db()
    with pytest.raises(ProgramTerminatedError, match="No logged-in Evernote desktop"):
        extract_token(config_dir=fake.config_dir)


def test_extract_token_missing_secure_storage_raises(tmp_path):
    fake = FakeDesktopSession(tmp_path)
    fake.write(write_storage=False)
    with pytest.raises(ProgramTerminatedError, match="Secure-storage file"):
        extract_token(user_id=fake.user_id, config_dir=fake.config_dir)


def test_extract_token_key_missing_raises(fake_desktop_session, monkeypatch):
    monkeypatch.setattr("keyring.get_password", lambda service, account: None)

    with pytest.raises(ProgramTerminatedError, match="No Evernote encryption key"):
        extract_token(
            user_id=fake_desktop_session.user_id,
            config_dir=fake_desktop_session.config_dir,
        )


def test_extract_token_uses_default_config_dir(tmp_path, monkeypatch):
    fake = FakeDesktopSession(tmp_path)
    fake.write()
    fake.patch_keyring(monkeypatch)
    monkeypatch.setattr(
        "evernote_backup.desktop_session._default_config_dir",
        lambda: fake.config_dir,
    )
    session = extract_token(user_id=fake.user_id)
    assert session.s_token == fake.s_token
