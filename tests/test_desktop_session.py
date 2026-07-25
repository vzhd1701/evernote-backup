"""Tests for the Evernote-desktop-session token extractor."""
import base64
import json
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest
from cryptography.hazmat.primitives.ciphers import Cipher, algorithms, modes
from cryptography.hazmat.backends import default_backend

from evernote_backup.cli_app_util import ProgramTerminatedError
from evernote_backup.desktop_session import (
    DesktopSession,
    _decrypt_secure_blob,
    _default_config_dir,
    extract_token,
    list_desktop_users,
)


# ---- helpers ---------------------------------------------------------------

FAKE_USER_ID = "151636"
FAKE_USERNAME = "beernutz"
FAKE_EMAIL = "beernutz@gmail.com"
FAKE_S_TOKEN = "S=s3:U=25054:E=19f97d7cee2:C=19f9769f1e2:P=1dd:A=en-w32-xauth-new:V=2:H=deadbeef"
FAKE_SHARD = "s3"
FAKE_HOST = "www.evernote.com"
FAKE_JWT = "eyJhbGciOiJIUzI1NiJ9.fake.fake"
FAKE_AES_KEY = b"\x11" * 32  # 32 bytes of 0x11
FAKE_IV = b"\x22" * 16


def _encrypt_userstore_blob(plaintext_json: bytes) -> tuple[bytes, bytes]:
    """Encrypt with AES-256-CBC + PKCS7, return (ciphertext, iv)."""
    pad = 16 - (len(plaintext_json) % 16)
    padded = plaintext_json + bytes([pad]) * pad
    iv = b"\x33" * 16
    cipher = Cipher(algorithms.AES(FAKE_AES_KEY), modes.CBC(iv), backend=default_backend())
    enc = cipher.encryptor()
    return enc.update(padded) + enc.finalize(), iv


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


def _write_multiuser_db(db_path: Path, user_id: str = FAKE_USER_ID,
                        username: str = FAKE_USERNAME,
                        email: str = FAKE_EMAIL) -> None:
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
    db = cfg / "conduit-storage" / "https%3A%2F%2Fwww.evernote.com" / "_ConduitMultiUserDB.sql"
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


# ---- extract_token (with mocked OS key) -------------------------------------


def test_extract_token_windows(fake_evernote_dir, monkeypatch):
    """End-to-end extraction with a mocked Windows Credential Manager read."""
    fake_cred_blob = b"enote-encr-key" + base64.b64encode(FAKE_AES_KEY)

    fake_cred = MagicMock()
    fake_cred.__getitem__.side_effect = lambda k: {
        "TargetName": f"Evernote/AuthToken:User:{FAKE_USER_ID}",
        "CredentialBlob": fake_cred_blob,
    }[k]

    fake_win32cred = MagicMock()
    fake_win32cred.CredRead.return_value = fake_cred
    fake_win32cred.CRED_TYPE_GENERIC = 1

    monkeypatch.setitem(sys_modules := __import__("sys").modules, "win32cred", fake_win32cred)

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
    pad = 16 - (len(plaintext) % 16)
    padded = plaintext + bytes([pad]) * pad
    iv = b"\x33" * 16
    cipher = Cipher(algorithms.AES(FAKE_AES_KEY), modes.CBC(iv), backend=default_backend())
    enc = cipher.encryptor()
    ciphertext = enc.update(padded) + enc.finalize()
    blob_path = fake_evernote_dir / "secure-storage" / f"authtoken_user_{FAKE_USER_ID}"
    blob_path.write_text(json.dumps({
        "iv": base64.b64encode(iv).decode("ascii"),
        "encrypted": ciphertext.decode("latin-1"),
    }), encoding="utf-8")

    fake_cred = MagicMock()
    fake_cred.__getitem__.side_effect = lambda k: {
        "CredentialBlob": b"enote-encr-key" + base64.b64encode(FAKE_AES_KEY),
    }[k]
    fake_win32cred = MagicMock()
    fake_win32cred.CredRead.return_value = fake_cred
    monkeypatch.setitem(__import__("sys").modules, "win32cred", fake_win32cred)

    with pytest.raises(ProgramTerminatedError, match="no 't' \\(token\\) field"):
        extract_token(user_id=FAKE_USER_ID, config_dir=fake_evernote_dir)


def test_extract_token_missing_user_raises(fake_evernote_dir, monkeypatch):
    fake_win32cred = MagicMock()
    monkeypatch.setitem(__import__("sys").modules, "win32cred", fake_win32cred)
    with pytest.raises(ProgramTerminatedError, match="not found"):
        extract_token(user_id="999999", config_dir=fake_evernote_dir)


def test_extract_token_cred_read_error_raises(fake_evernote_dir, monkeypatch):
    fake_win32cred = MagicMock()
    fake_win32cred.CredRead.side_effect = Exception("access denied")
    fake_win32cred.CRED_TYPE_GENERIC = 1
    monkeypatch.setitem(__import__("sys").modules, "win32cred", fake_win32cred)

    with pytest.raises(ProgramTerminatedError, match="Could not read Windows credential"):
        extract_token(user_id=FAKE_USER_ID, config_dir=fake_evernote_dir)


# ---- _default_config_dir per platform --------------------------------------


def test_default_config_dir_windows(monkeypatch):
    monkeypatch.setattr("sys.platform", "win32")
    monkeypatch.setenv("APPDATA", r"C:\Users\scott\AppData\Roaming")
    assert _default_config_dir() == Path(r"C:\Users\scott\AppData\Roaming\Evernote")


def test_default_config_dir_darwin(monkeypatch):
    monkeypatch.setattr("sys.platform", "darwin")
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setattr("pathlib.Path.home",
                        lambda: Path("/Users/scott"), raising=False)
    assert _default_config_dir() == Path("/Users/scott/Library/Application Support/Evernote")


def test_default_config_dir_linux_xdg(monkeypatch):
    monkeypatch.setattr("sys.platform", "linux")
    monkeypatch.delenv("APPDATA", raising=False)
    monkeypatch.setenv("XDG_CONFIG_HOME", "/home/scott/.config")
    assert _default_config_dir() == Path("/home/scott/.config/Evernote")
