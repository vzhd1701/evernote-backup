import base64
import time
from typing import Optional


def fmt_time(timestamp: Optional[int]) -> Optional[str]:
    if timestamp is None:
        return timestamp
    return time.strftime("%Y%m%dT%H%M%SZ", time.gmtime(timestamp // 1000))


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
