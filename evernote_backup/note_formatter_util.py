import base64
import sys
from collections.abc import Iterator
from datetime import UTC, datetime, timedelta

BINARY_LINE_WIDTH = 120

# 120 base64 characters encode exactly 90 source bytes, so a chunk boundary
# always lands on a line boundary and chunks can be emitted independently.
BINARY_CHUNK_SIZE = 90 * 4096


def fmt_utcfromtimestamp(timestamp: int) -> datetime:
    return datetime.fromtimestamp(timestamp, tz=UTC)


def fmt_time(timestamp: int | None) -> str | None:
    if timestamp is None:
        return timestamp

    timestamp //= 1000

    # https://dev.evernote.com/doc/reference/Types.html#Typedef_Timestamp
    if timestamp < 0:
        date = _date_from_past(timestamp)
    elif timestamp >= _get_max_timestamp():
        date = _date_from_future(timestamp)
    else:
        date = fmt_utcfromtimestamp(timestamp)

    return date.strftime(f"{date.year:04}%m%dT%H%M%SZ")


def iter_binary(binary_data: bytes) -> Iterator[str]:
    """Emit the base64 body chunk by chunk.

    Encoding a resource in one go costs several times its size in intermediate
    strings, which is the dominant memory peak of an export.
    """
    yield "\n"

    for offset in range(0, len(binary_data), BINARY_CHUNK_SIZE):
        if offset:
            yield "\n"

        encoded = base64.b64encode(
            binary_data[offset : offset + BINARY_CHUNK_SIZE]
        ).decode()

        yield _slice_str(encoded, BINARY_LINE_WIDTH)

    yield "\n      "


def fmt_binary(binary_data: bytes) -> str:
    return "".join(iter_binary(binary_data))


def fmt_content(content_body: str | None) -> str | None:
    if content_body is None:
        return content_body

    body = content_body.strip()

    # <?xml version="1.0" encoding="UTF-8"?>
    if body.startswith("<?xml") and body.find(">") != -1:
        content_start = body.find(">") + 1
        body = body[content_start:].strip()

    # A CDATA section cannot be escaped from within, so a literal "]]>" in the
    # body has to be split across two sections, or it would terminate the
    # section early and spill the rest of the note out as markup.
    # https://www.w3.org/TR/xml/#sec-cdata-sect
    body = body.replace("]]>", "]]]]><![CDATA[>")

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
        is_64bits = sys.maxsize > 2**32
        return int(
            datetime(
                3000,
                1,
                1,
                23,
                59,
                59,
                999999,
                tzinfo=UTC,
            ).timestamp()
            if is_64bits
            else datetime(
                2038,
                1,
                1,
                23,
                59,
                59,
                999999,
                tzinfo=UTC,
            ).timestamp()
        )


# https://stackoverflow.com/a/42936293/13100286
# https://howardhinnant.github.io/date_algorithms.html#civil_from_days
def _date_from_future(timestamp: int) -> datetime:
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

    try:
        day_time = fmt_utcfromtimestamp(timestamp % 86400)

        return datetime(
            year=y,
            month=m,
            day=d,
            hour=day_time.hour,
            minute=day_time.minute,
            second=day_time.second,
            tzinfo=UTC,
        )
    except (OverflowError, ValueError, OSError):
        return datetime.max


def _date_from_past(timestamp: int) -> datetime:
    try:
        return fmt_utcfromtimestamp(0) - timedelta(seconds=abs(timestamp))
    except (OverflowError, ValueError, OSError):
        return datetime.min
