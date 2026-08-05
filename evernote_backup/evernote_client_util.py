from enum import Enum
from typing import NamedTuple, Union

from evernote.edam.error.ttypes import (
    EDAMErrorCode,
    EDAMSystemException,
    EDAMUserException,
)

from evernote_backup.errors import EvernoteAuthError


class NoteStoreAccess(Enum):
    """How this NoteStore client is being used for downloads."""

    OWN = "own"  # home account: listTags for names
    LINKED_NOTEBOOK = "linked"  # shared notebook: listTagsByNotebook
    SINGLE_NOTE_SHARE = "single_share"  # single shared note: no tag API access


class NotebookAuth(NamedTuple):
    token: str
    shard: str
    access: NoteStoreAccess = NoteStoreAccess.OWN


def raise_auth_error(exception: Union[EDAMSystemException, EDAMUserException]) -> None:
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

    if isinstance(exception, EDAMSystemException):
        error_param = exception.message
    else:
        error_param = exception.parameter

    try:
        error = messages[exception.errorCode][error_param]
    except KeyError:
        return

    raise EvernoteAuthError(error)
