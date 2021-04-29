import time
from http.client import HTTPException
from typing import Any, Callable

from evernote_backup.config import NETWORK_ERROR_RETRY_COUNT


class EvernoteAuthError(Exception):
    """Evernote authentication error"""


def network_retry(fun: Callable) -> Callable:
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        retry_count = NETWORK_ERROR_RETRY_COUNT

        for i in range(retry_count):
            try:
                return fun(*args, **kwargs)
            except (HTTPException, ConnectionError):
                if i == retry_count - 1:
                    raise
                time.sleep(0.5)

    return wrapper
