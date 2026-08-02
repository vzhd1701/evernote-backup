from typing import Optional


class OAuthDeclinedError(Exception):
    def __init__(self, error: Optional[str] = None) -> None:
        self.error = error
        message = f"OAuth declined: {error}" if error else "OAuth declined"
        super().__init__(message)


class OAuthTokenRefreshError(Exception):
    """Raise when refresh_token grant fails."""


class ProgramTerminatedError(Exception):
    """Terminate program with an error"""


class DatabaseEmptyError(Exception):
    """Raise when database is empty"""


class DatabaseCorruptError(Exception):
    """Raise when database is corrupt"""


class EvernoteAuthError(Exception):
    """Evernote authentication error"""


class DatabaseResyncRequiredError(Exception):
    """Raise when database update requires resync"""


class WrongAuthUserError(Exception):
    """Raise when remote auth user is not the same as the one registered in database"""

    def __init__(self, local_user: str, remote_user: str) -> None:
        self.local_user = local_user
        self.remote_user = remote_user


class WorkerStopException(Exception):
    """Raise when workers are stopped"""


class NoteDownloadException(Exception):
    """Raise when downloading note fails"""
