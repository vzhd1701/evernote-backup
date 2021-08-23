from evernote.edam.error.ttypes import EDAMUserException
from evernote.edam.userstore.ttypes import AuthenticationResult

from evernote_backup.evernote_client import EvernoteClient
from evernote_backup.evernote_client_util import raise_auth_error


class EvernoteClientAuth(EvernoteClient):
    def __init__(
        self,
        backend: str,
        network_error_retry_count: int,
        consumer_key: str,
        consumer_secret: str,
    ):
        super().__init__(  # noqa: S106
            backend=backend,
            token="",
            network_error_retry_count=network_error_retry_count,
        )

        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret

    def login(self, username: str, password: str) -> AuthenticationResult:
        try:
            return self.user_store.authenticateLongSessionV2(
                username=username,
                password=password,
                ssoLoginToken=None,
                consumerKey=self.consumer_key,
                consumerSecret=self.consumer_secret,
                deviceIdentifier=None,
                deviceDescription=self.device_description,
                supportsTwoFactor=True,
                supportsBusinessOnlyAccounts=True,
            )
        except EDAMUserException as e:
            raise_auth_error(e)
            raise

    def two_factor_auth(self, auth_token: str, ota_code: str) -> AuthenticationResult:
        try:
            return self.user_store.completeTwoFactorAuthentication(
                authenticationToken=auth_token,
                oneTimeCode=ota_code,
                deviceIdentifier=None,
                deviceDescription=self.device_description,
            )
        except EDAMUserException as e:
            raise_auth_error(e)
            raise
