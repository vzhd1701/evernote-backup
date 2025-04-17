from datetime import datetime

from evernote_backup.note_formatter_util import fmt_utcfromtimestamp


def get_token_expiration_date(token: str) -> datetime:
    hex_base = 16
    token_parts = token.split(":")
    token_expire_ts = int(token_parts[2][2:], base=hex_base) // 1000

    return fmt_utcfromtimestamp(token_expire_ts)


def get_token_shard(token: str) -> str:
    return token[2 : token.index(":")]
