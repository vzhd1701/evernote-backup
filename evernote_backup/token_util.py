from dataclasses import dataclass
from datetime import datetime, timezone


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
