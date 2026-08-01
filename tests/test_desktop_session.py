"""Tests for the Evernote-desktop-session token extractor."""

import base64
import json
import sqlite3
import sys
from pathlib import Path

import pytest

from evernote_backup.cli_app_util import ProgramTerminatedError
from evernote_backup.desktop_session import (
    DesktopSession,
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

# ---- helpers ---------------------------------------------------------------

FAKE_USER_ID = "151636"
FAKE_USERNAME = "beernutz"
FAKE_EMAIL = "beernutz@gmail.com"
FAKE_S_TOKEN = (
    "S=s3:U=25054:E=19f97d7cee2:C=19f9769f1e2:P=1dd:A=en-w32-xauth-new:V=2:H=deadbeef"
)
FAKE_SHARD = "s3"
FAKE_HOST = "www.evernote.com"
FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9.fake.fake"
FAKE_AES_KEY = b"\x11" * 32  # 32 bytes of 0x11
FAKE_IV = b"\x22" * 16


def _encrypt_userstore_blob(plaintext_json: bytes) -> tuple[bytes, bytes]:
    """Encrypt with AES-256-CBC + PKCS7, return (ciphertext, iv)."""
    from Crypto.Cipher import AES
    from Crypto.Util.Padding import pad

    iv = b"\x33" * 16
    cipher = AES.new(FAKE_AES_KEY, AES.MODE_CBC, iv)
    return cipher.encrypt(pad(plaintext_json, AES.block_size)), iv


def _build_userstore_payload() -> bytes:
    """Build a base64(JSON) payload matching Evernote's secure-storage layout."""
    payload = {
        "t": FAKE_S_TOKEN,
        "sh": FAKE_SHARD,
        "h": FAKE_HOST,
        "j": FAKE_JWT,
    }
    return base64.b64encode(json.dumps(payload).encode("utf-8"))


def _write_secure_storage(path: Path) -> None:
    """Write a realistic secure-storage JSON file at *path*."""
    plaintext = _build_userstore_payload()
    ciphertext, iv = _encrypt_userstore_blob(plaintext)
    blob = {
        "iv": base64.b64encode(iv).decode("ascii"),
        # Evernote writes each raw byte as one ISO-8859-1 character in JSON.
        "encrypted": ciphertext.decode("latin-1"),
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(blob), encoding="utf-8")


def _write_multiuser_db(
    db_path: Path,
    user_id: str = FAKE_USER_ID,
    username: str = FAKE_USERNAME,
    email: str = FAKE_EMAIL,
) -> None:
    """Write a minimal _ConduitMultiUserDB.sql with one user."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(str(db_path))
    con.execute("CREATE TABLE MultiUsers (Tkey TEXT, TValue TEXT)")
    con.execute(
        "INSERT INTO MultiUsers VALUES (?, ?)",
        (f"User:{user_id}", json.dumps({"username": username, "email": email})),
    )
    con.commit()
    con.close()


@pytest.fixture
def fake_evernote_dir(tmp_path: Path) -> Path:
    """Build a fake Evernote user-config directory with one logged-in user."""
    cfg = tmp_path / "Evernote"
    db = (
        cfg
        / "conduit-storage"
        / "https%3A%2F%2Fwww.evernote.com"
        / "_ConduitMultiUserDB.sql"
    )
    _write_multiuser_db(db)
    _write_secure_storage(cfg / "secure-storage" / f"authtoken_user_{FAKE_USER_ID}")
    return cfg


# ---- list_desktop_users -----------------------------------------------------


def test_list_users_no_db(tmp_path):
    with pytest.raises(ProgramTerminatedError, match="not found"):
        list_desktop_users(tmp_path / "Evernote")


def test_list_users_returns_logged_in_user(fake_evernote_dir):
    users = list_desktop_users(fake_evernote_dir)
    assert len(users) == 1
    u = users[0]
    assert u.user_id == FAKE_USER_ID
    assert u.username == FAKE_USERNAME
    assert u.email == FAKE_EMAIL
    # Secure-storage path is populated but token not yet decrypted
    assert u.s_token == ""
    assert u.storage_path == (
        fake_evernote_dir / "secure-storage" / f"authtoken_user_{FAKE_USER_ID}"
    )


# ---- _decrypt_secure_blob ---------------------------------------------------


def test_decrypt_secure_blob_roundtrip(fake_evernote_dir):
    blob_path = fake_evernote_dir / "secure-storage" / f"authtoken_user_{FAKE_USER_ID}"
    data = _decrypt_secure_blob(blob_path, FAKE_AES_KEY)
    assert data["t"] == FAKE_S_TOKEN
    assert data["sh"] == FAKE_SHARD
    assert data["h"] == FAKE_HOST
    assert data["j"] == FAKE_JWT


def test_decrypt_secure_blob_wrong_key_raises(fake_evernote_dir):
    blob_path = fake_evernote_dir / "secure-storage" / f"authtoken_user_{FAKE_USER_ID}"
    with pytest.raises(ProgramTerminatedError, match="PKCS7"):
        _decrypt_secure_blob(blob_path, b"\x00" * 32)


def test_decrypt_secure_blob_wrong_key_length_raises(fake_evernote_dir):
    blob_path = fake_evernote_dir / "secure-storage" / f"authtoken_user_{FAKE_USER_ID}"
    with pytest.raises(ProgramTerminatedError, match="key length"):
        _decrypt_secure_blob(blob_path, b"\x00" * 16)


# ---- OS key via keyring -----------------------------------------------------


def _fake_keyring_secret() -> str:
    """Build the string keyring returns for the AES key.

    On Windows Evernote stores the credential as raw ASCII bytes; keyring's
    WinVault backend decodes CredentialBlob as UTF-16, so get_password
    returns the misinterpreted string. Re-encoding with utf-16-le restores
    the original. On macOS the secret is a normal UTF-8 string.
    """
    raw = b"enote-encr-key" + base64.b64encode(FAKE_AES_KEY)
    if sys.platform.startswith("win"):
        return raw.decode("utf-16")
    return raw.decode("utf-8")


def test_keyring_service_and_account_windows(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    service, account = _keyring_service_and_account(FAKE_USER_ID)
    assert account == f"AuthToken:User:{FAKE_USER_ID}"
    assert service == f"Evernote/AuthToken:User:{FAKE_USER_ID}"


def test_keyring_service_and_account_darwin(monkeypatch):
    monkeypatch.setattr("sys.platform", "darwin")
    service, account = _keyring_service_and_account(FAKE_USER_ID)
    assert account == f"AuthToken:User:{FAKE_USER_ID}"
    assert service == "Evernote"


def test_get_os_key_roundtrip(monkeypatch):
    monkeypatch.setattr(
        "keyring.get_password", lambda service, account: _fake_keyring_secret()
    )
    assert _get_os_key(FAKE_USER_ID) == FAKE_AES_KEY


def test_get_os_key_missing_raises(monkeypatch):
    monkeypatch.setattr("keyring.get_password", lambda service, account: None)
    with pytest.raises(ProgramTerminatedError, match="No Evernote encryption key"):
        _get_os_key(FAKE_USER_ID)


def test_get_os_key_locked_raises(monkeypatch):
    from keyring.errors import KeyringLocked

    def _raise(*_a, **_k):
        raise KeyringLocked("locked")

    monkeypatch.setattr("keyring.get_password", _raise)
    with pytest.raises(ProgramTerminatedError, match="locked"):
        _get_os_key(FAKE_USER_ID)


# ---- extract_token (with mocked OS key) -------------------------------------


def test_extract_token(fake_evernote_dir, monkeypatch):
    """End-to-end extraction with a mocked keyring read."""
    monkeypatch.setattr(
        "keyring.get_password", lambda service, account: _fake_keyring_secret()
    )

    session = extract_token(user_id=FAKE_USER_ID, config_dir=fake_evernote_dir)
    assert session.s_token == FAKE_S_TOKEN
    assert session.shard == FAKE_SHARD
    assert session.host == FAKE_HOST
    assert session.jwt_access == FAKE_JWT
    assert session.user_id == FAKE_USER_ID
    assert session.username == FAKE_USERNAME
    assert session.email == FAKE_EMAIL


def test_extract_token_no_token_field_raises(fake_evernote_dir, monkeypatch):
    """If the decrypted blob has no 't' field, surface a clear error."""
    payload = base64.b64encode(b'{"sh": "s3", "h": "www.evernote.com"}')
    plaintext = payload
    ciphertext, iv = _encrypt_userstore_blob(plaintext)
    blob_path = fake_evernote_dir / "secure-storage" / f"authtoken_user_{FAKE_USER_ID}"
    blob_path.write_text(
        json.dumps(
            {
                "iv": base64.b64encode(iv).decode("ascii"),
                "encrypted": ciphertext.decode("latin-1"),
            }
        ),
        encoding="utf-8",
    )

    monkeypatch.setattr(
        "keyring.get_password", lambda service, account: _fake_keyring_secret()
    )

    with pytest.raises(ProgramTerminatedError, match="no 't' \\(token\\) field"):
        extract_token(user_id=FAKE_USER_ID, config_dir=fake_evernote_dir)


def test_extract_token_missing_user_raises(fake_evernote_dir):
    with pytest.raises(ProgramTerminatedError, match="not found"):
        extract_token(user_id="999999", config_dir=fake_evernote_dir)


def test_extract_token_key_missing_raises(fake_evernote_dir, monkeypatch):
    monkeypatch.setattr("keyring.get_password", lambda service, account: None)

    with pytest.raises(ProgramTerminatedError, match="No Evernote encryption key"):
        extract_token(user_id=FAKE_USER_ID, config_dir=fake_evernote_dir)


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
