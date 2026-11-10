"""Send a renewed session's cookie with the response (Users and roles in docs/SPEC.md).

`auth.get_principal` renews a session in use when less than half its time is left and
leaves the new Set-Cookie header in the request's state; this adds it to the response,
whatever the route returns.
"""

from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from filament_tracker.auth import RENEWED_COOKIE


class SessionRenewalMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        async def send_with_cookie(message: Message) -> None:
            if message["type"] == "http.response.start":
                cookie = scope.get("state", {}).get(RENEWED_COOKIE)
                if cookie:
                    MutableHeaders(scope=message).append("set-cookie", cookie)
            await send(message)

        await self.app(scope, receive, send_with_cookie)
