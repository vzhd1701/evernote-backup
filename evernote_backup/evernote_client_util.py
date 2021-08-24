import time
from http.client import HTTPException
from typing import Any, Callable, NamedTuple, Union

from evernote.edam.error.ttypes import (
    EDAMErrorCode,
    EDAMSystemException,
    EDAMUserException,
)


class NotebookAuth(NamedTuple):
    token: str
    shard: str


class EvernoteAuthError(Exception):
    """Evernote authentication error"""


def network_retry(network_error_retry_count: int) -> Callable:
    def decorator(fun: Callable) -> Callable:
        def wrapper(*args: Any, **kwargs: Any) -> Any:
            retry_count = network_error_retry_count

            for i in range(network_error_retry_count):
                try:
                    return fun(*args, **kwargs)
                except (HTTPException, ConnectionError):
                    if i == retry_count - 1:
                        raise
                    time.sleep(0.5)

        return wrapper

    return decorator


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
                " Use --oauth option to log in."
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
