from typing import Optional


class OAuthDeclinedError(Exception):
    def __init__(self, error: Optional[str] = None) -> None:
        self.error = error
        message = f"OAuth declined: {error}" if error else "OAuth declined"
        super().__init__(message)


class OAuthTokenRefreshError(Exception):
    """Raise when refresh_token grant fails."""
