"""Vercel entry point: every request is rewritten here (see vercel.json).

The rewrite sends `/anything?x=1` to `/api/index?__path=anything&x=1`, because
the function otherwise sees its own path (`/api/index`) instead of the page
that was asked for. `restore_path` puts the original path back before FastAPI
routes the request.
"""

import sys
from pathlib import Path
from urllib.parse import parse_qsl, urlencode

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from tradelab.web.app import app as fastapi_app  # noqa: E402

ENTRY = "/api/index"
PARAM = "__path"


def restore_path(inner):
    async def asgi(scope, receive, send):
        if scope.get("type") in ("http", "websocket") and scope.get("path", "").startswith(ENTRY):
            pairs = parse_qsl(scope.get("query_string", b"").decode("latin-1"), keep_blank_values=True)
            wanted = next((v for k, v in pairs if k == PARAM), None)
            if wanted is not None:
                path = "/" + wanted.lstrip("/")
                rest = urlencode([(k, v) for k, v in pairs if k != PARAM])
                scope = dict(scope, path=path, raw_path=path.encode(), query_string=rest.encode("latin-1"))
        await inner(scope, receive, send)
    return asgi


app = restore_path(fastapi_app)
