from typing import Optional

from evernote.edam.error.ttypes import EDAMUserException
from evernote.edam.userstore.ttypes import (
    AuthenticationParameters,
    AuthenticationResult,
)

from evernote_backup.evernote_client import EvernoteClient
from evernote_backup.evernote_client_util import raise_auth_error


class EvernoteClientAuth(EvernoteClient):
    def __init__(
        self,
        backend: str,
        network_error_retry_count: int,
        consumer_key: str,
        consumer_secret: str,
        cafile: Optional[str],
    ):
        super().__init__(
            backend=backend,
            token="",
            network_error_retry_count=network_error_retry_count,
            cafile=cafile,
        )

        self.consumer_key = consumer_key
        self.consumer_secret = consumer_secret

    def login(self, username: str, password: str) -> AuthenticationResult:
        auth_params = AuthenticationParameters(
            usernameOrEmail=username,
            password=password,
            ssoLoginToken="",
            consumerKey=self.consumer_key,
            consumerSecret=self.consumer_secret,
            deviceIdentifier="",
            deviceDescription=self.device_description,
            supportsTwoFactor=True,
            supportsBusinessOnlyAccounts=True,
        )

        try:
            return self.user_store.authenticateLongSessionV2(auth_params)
        except EDAMUserException as e:
            raise_auth_error(e)
            raise

    def two_factor_auth(self, auth_token: str, ota_code: str) -> AuthenticationResult:
        try:
            self.token = auth_token
            return self.user_store.completeTwoFactorAuthentication(
                oneTimeCode=ota_code,
                deviceIdentifier="",
                deviceDescription=self.device_description,
            )
        except EDAMUserException as e:
            raise_auth_error(e)
            raise
