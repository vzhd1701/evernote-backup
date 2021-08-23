from datetime import datetime


def get_token_expiration_date(token: str) -> datetime:
    hex_base = 16
    token_parts = token.split(":")
    token_expire_ts = int(token_parts[2][2:], base=hex_base) // 1000

    return datetime.utcfromtimestamp(token_expire_ts)


def get_token_shard(token: str) -> str:
    if not token:
        return ""

    return token[2 : token.index(":")]
