"""Run the studio on AWS Lambda behind a function URL.

`handler` turns one function URL event into one WSGI request for `studio.app`.
"""

from __future__ import annotations

import base64
import io
import sys
from typing import Any

from studio.app import application

# The answers that go out as text. Each other answer goes out as base64.
TEXT = ("text/", "application/json")


def handler(event: dict[str, Any], context: Any = None) -> dict[str, Any]:
    """Answer one function URL event."""
    request = event.get("requestContext", {}).get("http", {})
    headers = event.get("headers") or {}
    body = event.get("body") or ""
    content = base64.b64decode(body) if event.get("isBase64Encoded") else body.encode()
    environ = {
        "REQUEST_METHOD": request.get("method", "GET"),
        "SCRIPT_NAME": "",
        "PATH_INFO": event.get("rawPath") or "/",
        "QUERY_STRING": event.get("rawQueryString") or "",
        "SERVER_NAME": headers.get("host", "lambda"),
        "SERVER_PORT": "443",
        "SERVER_PROTOCOL": "HTTP/1.1",
        "CONTENT_TYPE": headers.get("content-type", ""),
        "CONTENT_LENGTH": str(len(content)),
        "wsgi.version": (1, 0),
        "wsgi.url_scheme": "https",
        "wsgi.input": io.BytesIO(content),
        "wsgi.errors": sys.stderr,
        "wsgi.multithread": False,
        "wsgi.multiprocess": False,
        "wsgi.run_once": False,
    }
    seen: dict[str, Any] = {}

    def start_response(status: str, answer_headers: list[tuple[str, str]], exc_info: Any = None) -> None:
        seen.update(status=int(status.split()[0]), headers=dict(answer_headers))

    data = b"".join(application(environ, start_response))
    is_text = seen["headers"].get("Content-Type", "").startswith(TEXT)
    return {
        "statusCode": seen["status"],
        "headers": seen["headers"],
        "body": data.decode() if is_text else base64.b64encode(data).decode(),
        "isBase64Encoded": not is_text,
    }
