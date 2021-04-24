import time
from http.client import HTTPException


class EvernoteAuthError(Exception):
    """Evernote authentication error"""


def network_retry(fun):
    def wrapper(*args, **kwargs):
        retry_count = 50

        for i in range(retry_count):
            try:
                return fun(*args, **kwargs)
            except (HTTPException, ConnectionError):
                if i == retry_count - 1:
                    raise
                time.sleep(0.5)

    return wrapper
