from enum import Enum
from typing import Any, NamedTuple, TypeVar, cast

from evernote.edam.error.ttypes import (
    EDAMErrorCode,
    EDAMSystemException,
    EDAMUserException,
)

from evernote_backup.errors import EvernoteAuthError

T = TypeVar("T")


def thrift_attrs(obj: object) -> Any:
    """Access Thrift object fields that ty cannot see.

    Generated EDAM classes set attributes via super().__setattr__, so type
    checkers do not treat errorCode/message/etc. as instance attributes.
    """
    return cast(Any, obj)


class NoteStoreAccess(Enum):
    """How this NoteStore client is being used for downloads."""

    OWN = "own"  # home account: listTags for names
    LINKED_NOTEBOOK = "linked"  # shared notebook: listTagsByNotebook
    SINGLE_NOTE_SHARE = "single_share"  # single shared note: no tag API access


class NotebookAuth(NamedTuple):
    token: str
    shard: str
    access: NoteStoreAccess = NoteStoreAccess.OWN


def require(value: T | None) -> T:
    """Assert a Thrift field is present.

    Evernote EDAM marks nearly every field Optional on the wire. Call this when
    the API is expected to always return a value so type checkers see a non-None
    type and missing data fails loudly.
    """
    if value is None:
        raise RuntimeError("Evernote returned None for a required field")
    return value


def raise_auth_error(exception: EDAMSystemException | EDAMUserException) -> None:
    messages = {
        EDAMErrorCode.BAD_DATA_FORMAT: {"authenticationToken": "Wrong token format!"},
        EDAMErrorCode.INVALID_AUTH: {
            "username": "Username not found!",
            "password": "Invalid password!",
            "oneTimeCode": "Invalid one-time code!",
            "authenticationToken": "Invalid authentication token!",
        },
        EDAMErrorCode.AUTH_EXPIRED: {
            "authenticationToken": "Authentication token expired or revoked!",
            "password": (
                "Password login disabled. Password reset required!\n"
                "Most probably, you log in to Evernote with Google or Apple account."
            ),
        },
    }

    exc = thrift_attrs(exception)
    if isinstance(exception, EDAMSystemException):
        error_param = exc.message
    else:
        error_param = exc.parameter

    try:
        error = messages[exc.errorCode][error_param]
    except KeyError:
        return

    raise EvernoteAuthError(error)
