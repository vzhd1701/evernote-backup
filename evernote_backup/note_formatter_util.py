import base64
import sys
from datetime import datetime
from typing import Optional


def fmt_time(timestamp: Optional[int]) -> Optional[str]:
    if timestamp is None:
        return timestamp

    timestamp //= 1000

    if timestamp < _get_max_timestamp():
        date = datetime.utcfromtimestamp(timestamp)
    else:
        date = _date_from_future(timestamp)

    return date.strftime("%Y%m%dT%H%M%SZ")


def fmt_binary(binary_data: bytes) -> str:
    slice_width = 120
    return (
        "\n"
        + _slice_str(base64.b64encode(binary_data).decode(), slice_width)
        + "\n      "
    )


def fmt_content(content_body: Optional[str]) -> Optional[str]:
    if content_body is None:
        return content_body

    body = content_body.strip()

    # <?xml version="1.0" encoding="UTF-8"?>
    if body.startswith("<?xml") and body.find(">") != -1:
        content_start = body.find(">") + 1
        body = body[content_start:].strip()

    return (
        f"\n      "
        f"<![CDATA["
        f'<?xml version="1.0" encoding="UTF-8" standalone="no"?>\n'
        f"{body}"
        f"]]>\n    "
    )


def _slice_str(text: str, width: int) -> str:
    slice_steps = range(0, len(text), width)
    slice_lines = (text[i : i + width] for i in slice_steps)
    return "\n".join(slice_lines)


# https://github.com/arrow-py/arrow/blob/10e8970baabeefd8c2f31814d66b11421ac128f1/arrow/constants.py
def _get_max_timestamp() -> int:  # pragma: no cover
    try:
        return int(datetime.max.timestamp())
    except (OverflowError, ValueError, OSError):
        is_64bits = sys.maxsize > 2 ** 32  # noqa: WPS114
        return int(
            datetime(3000, 1, 1, 23, 59, 59, 999999).timestamp()
            if is_64bits
            else datetime(2038, 1, 1, 23, 59, 59, 999999).timestamp()
        )


# https://stackoverflow.com/a/42936293/13100286
# https://howardhinnant.github.io/date_algorithms.html#civil_from_days
def _date_from_future(timestamp: int) -> datetime:  # noqa: WPS210
    z = timestamp // 86400 + 719468
    era = (z if z >= 0 else z - 146096) // 146097
    doe = z - era * 146097
    yoe = (doe - doe // 1460 + doe // 36524 - doe // 146096) // 365
    y = yoe + era * 400
    doy = doe - (365 * yoe + yoe // 4 - yoe // 100)
    mp = (5 * doy + 2) // 153
    d = doy - (153 * mp + 2) // 5 + 1
    m = mp + (3 if mp < 10 else -9)
    y += m <= 2

    day_time = datetime.utcfromtimestamp(timestamp % 86400)

    return datetime(
        year=y,
        month=m,
        day=d,
        hour=day_time.hour,
        minute=day_time.minute,
        second=day_time.second,
    )
