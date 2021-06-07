import time
from http.client import HTTPException
from typing import Any, Callable


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
