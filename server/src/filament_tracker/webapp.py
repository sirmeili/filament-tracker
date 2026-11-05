"""Serve the built web app (`web/build`) at `/` (Server: web UI in docs/SPEC.md).

The web app is a single-page app: any path that is not an API route or a file in the
build is answered with `index.html`, and the app shows the right page in the browser.

SvelteKit starts the app with one small inline script. Rather than allow inline scripts,
the Content Security Policy for `index.html` lists that script's SHA-256 hash, computed
from the built file when the server starts.
"""

import base64
import hashlib
import logging
import re
from pathlib import Path

from fastapi import FastAPI, HTTPException, Response
from fastapi.responses import FileResponse, HTMLResponse
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

from filament_tracker.api.security import CONTENT_SECURITY_POLICY

log = logging.getLogger(__name__)

# <script> elements without a src attribute, and their contents.
_INLINE_SCRIPT = re.compile(r"<script(?![^>]*\bsrc=)[^>]*>(.*?)</script>", re.DOTALL)
IMMUTABLE_CACHE = "public, max-age=31536000, immutable"


def default_web_dir() -> Path:
    """`web/build` in a source checkout (server/src/filament_tracker -> repository)."""
    return Path(__file__).resolve().parents[3] / "web" / "build"


def inline_script_hashes(html: str) -> list[str]:
    hashes = []
    for content in _INLINE_SCRIPT.findall(html):
        digest = hashlib.sha256(content.encode()).digest()
        hashes.append(f"'sha256-{base64.b64encode(digest).decode()}'")
    return hashes


def page_policy(html: str) -> str:
    """The app's Content Security Policy, allowing only the page's own inline scripts."""
    hashes = " ".join(inline_script_hashes(html))
    if not hashes:
        return CONTENT_SECURITY_POLICY
    return CONTENT_SECURITY_POLICY.replace("script-src 'self'", f"script-src 'self' {hashes}", 1)


class _Assets(StaticFiles):
    """Built assets. Files under `immutable/` have hashed names, so they never change."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        # Starlette gives the path with the platform's separator.
        if path.replace("\\", "/").startswith("immutable/") and response.status_code == 200:
            response.headers["Cache-Control"] = IMMUTABLE_CACHE
        return response


def mount_web_app(app: FastAPI, web_dir: Path) -> bool:
    """Serve the web app from `web_dir`. Returns False (and serves nothing) if it has not
    been built. Call after the API routers, so they take precedence."""
    index = web_dir / "index.html"
    if not index.is_file():
        log.info("web app not found at %s; serving the API only", web_dir)
        return False

    html = index.read_text(encoding="utf-8")
    headers = {"Content-Security-Policy": page_policy(html), "Cache-Control": "no-cache"}
    root = web_dir.resolve()
    if (root / "_app").is_dir():
        app.mount("/_app", _Assets(directory=root / "_app"), name="web-assets")

    @app.get("/{path:path}", include_in_schema=False)
    def web_page(path: str) -> Response:
        if path == "api" or path.startswith("api/"):
            raise HTTPException(404, "Not Found")
        candidate = (root / path).resolve()
        if path and candidate.is_file() and candidate.is_relative_to(root):
            return FileResponse(candidate)
        return HTMLResponse(html, headers=headers)

    return True
