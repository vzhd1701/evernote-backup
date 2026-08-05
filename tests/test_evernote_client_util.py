"""Unit tests for evernote_client_util helpers."""

import pytest
from evernote.edam.error.ttypes import (
    EDAMErrorCode,
    EDAMSystemException,
    EDAMUserException,
)

from evernote_backup.errors import EvernoteAuthError
from evernote_backup.evernote_client_util import (
    NotebookAuth,
    NoteStoreAccess,
    raise_auth_error,
    require,
    thrift_attrs,
)


def test_require_returns_value():
    assert require("x") == "x"
    assert require(0) == 0
    assert require(False) is False


def test_require_none_raises():
    with pytest.raises(RuntimeError, match="Evernote returned None"):
        require(None)


def test_thrift_attrs_exposes_fields():
    exc = EDAMSystemException(
        errorCode=EDAMErrorCode.RATE_LIMIT_REACHED,
        message="slow down",
        rateLimitDuration=60,
    )
    attrs = thrift_attrs(exc)
    assert attrs.errorCode == EDAMErrorCode.RATE_LIMIT_REACHED
    assert attrs.message == "slow down"
    assert attrs.rateLimitDuration == 60


def test_notebook_auth_defaults_to_own_access():
    auth = NotebookAuth(token="t", shard="s1")
    assert auth.access is NoteStoreAccess.OWN
    assert auth.token == "t"
    assert auth.shard == "s1"


@pytest.mark.parametrize(
    ("exception", "match"),
    [
        (
            EDAMSystemException(
                errorCode=EDAMErrorCode.BAD_DATA_FORMAT,
                message="authenticationToken",
            ),
            "Wrong token format",
        ),
        (
            EDAMUserException(
                errorCode=EDAMErrorCode.INVALID_AUTH,
                parameter="username",
            ),
            "Username not found",
        ),
        (
            EDAMUserException(
                errorCode=EDAMErrorCode.INVALID_AUTH,
                parameter="password",
            ),
            "Invalid password",
        ),
        (
            EDAMUserException(
                errorCode=EDAMErrorCode.INVALID_AUTH,
                parameter="oneTimeCode",
            ),
            "Invalid one-time code",
        ),
        (
            EDAMUserException(
                errorCode=EDAMErrorCode.INVALID_AUTH,
                parameter="authenticationToken",
            ),
            "Invalid authentication token",
        ),
        (
            EDAMUserException(
                errorCode=EDAMErrorCode.AUTH_EXPIRED,
                parameter="authenticationToken",
            ),
            "expired or revoked",
        ),
        (
            EDAMUserException(
                errorCode=EDAMErrorCode.AUTH_EXPIRED,
                parameter="password",
            ),
            "Password login disabled",
        ),
    ],
)
def test_raise_auth_error_known_messages(exception, match):
    with pytest.raises(EvernoteAuthError, match=match):
        raise_auth_error(exception)


def test_raise_auth_error_unknown_code_is_noop():
    raise_auth_error(
        EDAMUserException(
            errorCode=EDAMErrorCode.PERMISSION_DENIED,
            parameter="authenticationToken",
        )
    )


def test_raise_auth_error_unknown_param_is_noop():
    raise_auth_error(
        EDAMUserException(
            errorCode=EDAMErrorCode.INVALID_AUTH,
            parameter="not-a-mapped-field",
        )
    )
