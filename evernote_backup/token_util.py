import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

import jwt
import requests
from oauthlib.oauth2 import OAuth2Error
from requests_oauthlib import OAuth2Session

from evernote_backup.config_defaults import (
    TOKEN_REFRESH_SKEW,
    EVERNOTE_TOKEN_URL,
    EVERNOTE_API_USERS_ME_URL,
    DESKTOP_REDIRECT_URI,
    DESKTOP_CLIENT_ID,
)
from evernote_backup.errors import OAuthTokenRefreshError, ProgramTerminatedError

logger = logging.getLogger(__name__)


@dataclass
class EvernoteToken:
    shard: str
    user_id: int
    expiration: datetime
    creation: datetime
    agent: str

    shard_id: int
    raw: str

    def __str__(self) -> str:
        return self.raw

    @property
    def expiration_human(self) -> str:
        return _format_datetime_with_difference(self.expiration)

    @classmethod
    def from_string(cls, token_string: str) -> "EvernoteToken":
        try:
            return _parse_evernote_token(token_string)
        except Exception as e:
            raise ValueError(f"Invalid token format ({e}): {token_string}")


def _format_datetime_with_difference(dt: datetime) -> str:
    formatted_date = dt.strftime("%Y-%m-%d %H:%M:%S")

    now = datetime.now(timezone.utc)
    diff = dt - now

    if diff.total_seconds() < 0:
        diff = abs(diff)
        time_direction = "ago"
    else:
        time_direction = "left"

    total_seconds = diff.total_seconds()
    days = diff.days

    if days >= 1:
        time_diff = f"{days} day{'s' if days > 1 else ''}"
    elif total_seconds >= 3600:
        hours = round(total_seconds / 3600)
        time_diff = f"{hours} hour{'s' if hours > 1 else ''}"
    elif total_seconds >= 60:
        minutes = round(total_seconds / 60)
        time_diff = f"{minutes} minute{'s' if minutes > 1 else ''}"
    else:
        seconds = round(total_seconds)
        time_diff = f"{seconds} second{'s' if seconds != 1 else ''}"  # noqa: WPS504

    return f"{formatted_date} ({time_diff} {time_direction})"


def _parse_evernote_token(token: str) -> EvernoteToken:
    token_parts = {}

    for part in token.split(":"):
        key, value = part.split("=", 1)
        token_parts[key] = value

    required_keys = {"S", "U", "E", "C", "A"}
    missing_keys = required_keys - set(token_parts.keys())

    if missing_keys:
        raise ValueError(f"Token keys missing: {missing_keys}")

    shard_id = int(token_parts["S"][1:])
    user_id = int(token_parts["U"], 16)

    exp_ms = int(token_parts["E"], 16)
    creation_ms = int(token_parts["C"], 16)

    expiration_dt = datetime.fromtimestamp(exp_ms / 1000, tz=timezone.utc)
    creation_dt = datetime.fromtimestamp(creation_ms / 1000, tz=timezone.utc)

    return EvernoteToken(
        shard=token_parts["S"],
        user_id=user_id,
        expiration=expiration_dt,
        creation=creation_dt,
        agent=token_parts["A"],
        shard_id=shard_id,
        raw=token,
    )


@dataclass
class OAuth2TokenBundle:
    """OAuth2 token response as returned by Evernote /auth/token."""

    access_token: str
    refresh_token: str
    id_token: str
    expires_in: int
    token_type: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "access_token": self.access_token,
            "refresh_token": self.refresh_token,
            "id_token": self.id_token,
            "expires_in": self.expires_in,
            "token_type": self.token_type,
        }

    def to_json(self) -> str:
        return json.dumps(self.to_dict())

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> "OAuth2TokenBundle":
        try:
            return cls(
                access_token=data["access_token"],
                refresh_token=data["refresh_token"],
                id_token=data.get("id_token", ""),
                expires_in=int(data.get("expires_in", 0)),
                token_type=data.get("token_type", "Bearer"),
            )
        except KeyError as e:
            raise ValueError(f"OAuth2 token bundle missing field: {e}") from e

    @classmethod
    def from_json(cls, raw: str) -> "OAuth2TokenBundle":
        try:
            data = json.loads(raw)
        except json.JSONDecodeError as e:
            raise ValueError(f"Invalid OAuth2 token JSON: {e}") from e

        return cls.from_dict(data)

    @property
    def monolith_token(self) -> str:
        return str(decode_jwt(self.access_token)["mono_authn_token"])

    @property
    def access_expiration(self) -> datetime:
        exp = int(decode_jwt(self.access_token)["exp"])
        return datetime.fromtimestamp(exp, tz=timezone.utc)

    @property
    def monolith_expiration(self) -> datetime:
        return EvernoteToken.from_string(self.monolith_token).expiration

    @property
    def refresh_expiration(self) -> datetime:
        exp = int(decode_jwt(self.refresh_token)["exp"])
        return datetime.fromtimestamp(exp, tz=timezone.utc)

    @property
    def auth_time(self) -> datetime:
        """When the login session was initiated (authTime claim on refresh token)."""
        auth_time = int(decode_jwt(self.refresh_token)["authTime"])
        return datetime.fromtimestamp(auth_time, tz=timezone.utc)

    @property
    def auth_time_human(self) -> str:
        return _format_datetime_with_difference(self.auth_time)

    @property
    def needs_refresh(self) -> bool:
        now = datetime.now(timezone.utc)
        return (
            self.access_expiration - now <= TOKEN_REFRESH_SKEW
            or self.monolith_expiration - now <= TOKEN_REFRESH_SKEW
        )

    @property
    def is_refresh_expired(self) -> bool:
        return (
            self.refresh_expiration - datetime.now(timezone.utc) <= TOKEN_REFRESH_SKEW
        )


@dataclass
class ResolvedAuth:
    monolith_token: str
    jwt_token: Optional[str]
    auth_for_storage: str
    updated: bool


def decode_jwt(token: str) -> dict[str, Any]:
    try:
        return jwt.decode(token, options={"verify_signature": False})
    except jwt.PyJWTError as e:
        raise ValueError(f"Failed to decode JWT: {e}") from e


def get_client_id_from_refresh_token(refresh_token: str) -> str:
    return str(decode_jwt(refresh_token)["clientId"])


def resolve_auth_token(auth_token: str) -> ResolvedAuth:
    """
    Normalize stored / CLI auth into monolith + optional JWT.

    Accepts:
    - legacy monolith token (S=...)
    - bare OAuth2 refresh JWT
    - stored OAuth2 token bundle JSON (from /auth/token)

    When a JWT access token is available, verifies it against the Evernote
    users/me API and logs the authenticated user details.
    """
    raw = auth_token.strip()

    try:
        if _is_oauth_bundle_json(raw):
            return _resolve_oauth_bundle(OAuth2TokenBundle.from_json(raw))

        if _is_jwt_token(raw):
            logger.info("Refreshing OAuth2 access token from refresh token...")
            bundle = refresh_oauth_token(raw)
            verify_and_log_oauth_session(bundle)
            return ResolvedAuth(
                monolith_token=bundle.monolith_token,
                jwt_token=bundle.access_token,
                auth_for_storage=bundle.to_json(),
                updated=True,
            )

        # Legacy monolith token
        EvernoteToken.from_string(raw)
        return ResolvedAuth(
            monolith_token=raw,
            jwt_token=None,
            auth_for_storage=raw,
            updated=False,
        )
    except (ValueError, OAuthTokenRefreshError) as e:
        raise ProgramTerminatedError(str(e)) from e


def _is_oauth_bundle_json(raw: str) -> bool:
    return raw.strip().startswith("{")


def _is_jwt_token(raw: str) -> bool:
    try:
        decode_jwt(raw)
    except ValueError:
        return False

    return True


def _resolve_oauth_bundle(bundle: OAuth2TokenBundle) -> ResolvedAuth:
    if bundle.is_refresh_expired:
        raise ProgramTerminatedError(
            "OAuth2 refresh token is expired or about to expire."
            " Re-authenticate or provide a new refresh token."
        )

    is_updated = False

    if bundle.needs_refresh:
        logger.info("OAuth2 access token is expired or about to expire, refreshing...")
        bundle = refresh_oauth_token(bundle.refresh_token)
        is_updated = True

    verify_and_log_oauth_session(bundle)

    return ResolvedAuth(
        monolith_token=bundle.monolith_token,
        jwt_token=bundle.access_token,
        auth_for_storage=bundle.to_json(),
        updated=is_updated,
    )


def verify_and_log_oauth_session(bundle: OAuth2TokenBundle) -> dict[str, Any]:
    """Verify JWT access token via users/me and log user/session details."""
    user = fetch_oauth_current_user(bundle)

    user_id = user.get("id", "unknown")
    username = user.get("username") or "unknown"
    email = user.get("email") or "unknown"

    logger.info(
        f"Verified OAuth2 JWT for user ID {user_id}, username {username}, email {email}"
    )
    logger.info(f"Login session active since {bundle.auth_time_human}")

    return user


def fetch_oauth_current_user(bundle: OAuth2TokenBundle) -> dict[str, Any]:
    client_id = get_client_id_from_refresh_token(bundle.refresh_token)

    session = OAuth2Session(
        client_id=client_id,
        token={
            "access_token": bundle.access_token,
            "token_type": bundle.token_type or "Bearer",
        },
    )

    try:
        response = session.get(EVERNOTE_API_USERS_ME_URL, timeout=30)
        response.raise_for_status()
        data = response.json()
    except (requests.RequestException, ValueError, OAuth2Error) as e:
        raise ProgramTerminatedError(
            f"Failed to verify OAuth2 access token: {e}"
        ) from e

    if not isinstance(data, dict):
        raise ProgramTerminatedError(
            "Failed to verify OAuth2 access token: unexpected response format"
        )

    return data


def refresh_oauth_token(refresh_token: str) -> OAuth2TokenBundle:
    """
    Exchange a refresh_token for a new OAuth2 token bundle.
    """

    client_id = get_client_id_from_refresh_token(refresh_token)

    # does MCP need redirect_uri??
    redirect_uri = None
    if client_id.upper() == DESKTOP_CLIENT_ID.upper():
        redirect_uri = DESKTOP_REDIRECT_URI

    session = OAuth2Session(client_id=client_id)

    try:
        token = session.refresh_token(
            EVERNOTE_TOKEN_URL,
            client_id=client_id,
            refresh_token=refresh_token,
            redirect_uri=redirect_uri,
            timeout=30,
        )
    except (OAuth2Error, requests.RequestException) as e:
        raise OAuthTokenRefreshError(f"Token refresh failed: {e}") from e

    try:
        return OAuth2TokenBundle.from_dict(token)
    except ValueError as e:
        raise OAuthTokenRefreshError(str(e)) from e
