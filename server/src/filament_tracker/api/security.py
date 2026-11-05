"""Security headers on every response, and the API docs kept on the LAN (Security in
docs/SPEC.md).

The docs pages load Swagger UI and ReDoc from a CDN, so they get a looser policy; they
are only served to clients on `TRUSTED_NETWORKS`, and everyone else gets 404.
"""

from starlette.datastructures import MutableHeaders
from starlette.requests import HTTPConnection
from starlette.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from filament_tracker.config import Settings
from filament_tracker.net import is_trusted

DOCS_PATHS = frozenset({"/docs", "/docs/oauth2-redirect", "/redoc", "/openapi.json"})

CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self'",
        "style-src 'self' 'unsafe-inline'",
        "img-src 'self' data:",
        "connect-src 'self'",
        "object-src 'none'",
        "base-uri 'self'",
        "form-action 'self'",
        "frame-ancestors 'none'",
    ]
)
DOCS_CONTENT_SECURITY_POLICY = "; ".join(
    [
        "default-src 'self'",
        "script-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net",
        "style-src 'self' 'unsafe-inline' https://cdn.jsdelivr.net https://fonts.googleapis.com",
        "font-src 'self' https://fonts.gstatic.com",
        "img-src 'self' data: https://fastapi.tiangolo.com https://cdn.redoc.ly",
        "worker-src 'self' blob:",
        "connect-src 'self'",
        "object-src 'none'",
        "frame-ancestors 'none'",
    ]
)
COMMON_HEADERS = {
    "X-Frame-Options": "DENY",
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
}


class SecurityHeadersMiddleware:
    def __init__(self, app: ASGIApp, settings: Settings) -> None:
        self.app = app
        self.settings = settings

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        is_docs = scope["path"] in DOCS_PATHS
        if is_docs and not is_trusted(HTTPConnection(scope), self.settings):
            await JSONResponse({"detail": "Not Found"}, status_code=404)(scope, receive, send)
            return
        policy = DOCS_CONTENT_SECURITY_POLICY if is_docs else CONTENT_SECURITY_POLICY

        async def send_with_headers(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = MutableHeaders(scope=message)
                for name, value in COMMON_HEADERS.items():
                    headers.setdefault(name, value)
                headers.setdefault("Content-Security-Policy", policy)
            await send(message)

        await self.app(scope, receive, send_with_headers)
