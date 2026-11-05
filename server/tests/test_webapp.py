"""Serving the built web app: pages, assets, the SPA fallback and its CSP."""

import base64
import hashlib
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from filament_tracker.config import Settings
from filament_tracker.main import create_app
from filament_tracker.webapp import default_web_dir, inline_script_hashes, page_policy

BOOT = "\n  window.started = true;\n"
INDEX = f"""<!doctype html><html><head>
<link href="/_app/immutable/bundle.abc.js" rel="modulepreload">
<script src="/_app/immutable/other.js"></script>
</head><body><div><script>{BOOT}</script></div></body></html>"""


def _sha(text: str) -> str:
    return "'sha256-" + base64.b64encode(hashlib.sha256(text.encode()).digest()).decode() + "'"


@pytest.fixture
def web_dir(tmp_path: Path) -> Path:
    build = tmp_path / "build"
    (build / "_app" / "immutable").mkdir(parents=True)
    (build / "index.html").write_text(INDEX, encoding="utf-8")
    (build / "favicon.svg").write_text("<svg/>", encoding="utf-8")
    (build / "_app" / "immutable" / "bundle.abc.js").write_text("export {}", encoding="utf-8")
    (build / "_app" / "version.json").write_text('{"version":"1"}', encoding="utf-8")
    (tmp_path / "secret.txt").write_text("outside the build", encoding="utf-8")
    return build


@pytest.fixture
def client(db_url: str, web_dir: Path):  # noqa: ANN201
    app = create_app(Settings(database_url=db_url, web_dir=web_dir, _env_file=None))
    with TestClient(app) as client:
        yield client


def test_only_inline_scripts_are_hashed() -> None:
    assert inline_script_hashes(INDEX) == [_sha(BOOT)]


def test_a_page_without_inline_scripts_keeps_the_base_policy() -> None:
    assert "script-src 'self';" in page_policy("<html></html>")


@pytest.mark.parametrize("path", ["/", "/spools", "/spools/12", "/login?next=/review"])
def test_pages_get_the_app_with_a_hashed_policy(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 200
    assert response.text == INDEX
    policy = response.headers["content-security-policy"]
    assert f"script-src 'self' {_sha(BOOT)};" in policy
    assert "unsafe-inline" not in policy.split("script-src")[1].split(";")[0]
    assert response.headers["cache-control"] == "no-cache"
    assert response.headers["x-frame-options"] == "DENY"


def test_files_in_the_build_are_served(client: TestClient) -> None:
    assert client.get("/favicon.svg").text == "<svg/>"


def test_hashed_assets_are_cached_forever(client: TestClient) -> None:
    asset = client.get("/_app/immutable/bundle.abc.js")
    version = client.get("/_app/version.json")

    assert asset.status_code == 200
    assert asset.headers["cache-control"] == "public, max-age=31536000, immutable"
    assert "immutable" not in version.headers.get("cache-control", "")
    assert client.get("/_app/immutable/missing.js").status_code == 404


@pytest.mark.parametrize("path", ["/../secret.txt", "/%2e%2e/secret.txt", "/..%2fsecret.txt"])
def test_files_outside_the_build_are_never_served(client: TestClient, path: str) -> None:
    assert "outside the build" not in client.get(path).text


@pytest.mark.parametrize("path", ["/api", "/api/v1/nothing", "/api/v2/health"])
def test_unknown_api_paths_are_404_not_the_app(client: TestClient, path: str) -> None:
    response = client.get(path)

    assert response.status_code == 404
    assert response.json() == {"detail": "Not Found"}


def test_the_api_still_works(client: TestClient) -> None:
    assert client.get("/api/v1/health").json() == {"status": "ok"}


def test_without_a_build_only_the_api_is_served(db_url: str, tmp_path: Path) -> None:
    app = create_app(Settings(database_url=db_url, web_dir=tmp_path / "none", _env_file=None))
    with TestClient(app) as client:
        assert client.get("/").status_code == 404
        assert client.get("/api/v1/health").status_code == 200


def test_the_default_build_is_web_build_in_the_checkout() -> None:
    assert default_web_dir().parts[-2:] == ("web", "build")
    assert (default_web_dir().parent / "package.json").is_file()


def test_a_build_without_assets_still_serves_pages(db_url: str, tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text("<html></html>", encoding="utf-8")
    app = create_app(Settings(database_url=db_url, web_dir=tmp_path, _env_file=None))
    with TestClient(app) as client:
        assert client.get("/inventory").text == "<html></html>"
        assert client.get("/_app/immutable/x.js").text == "<html></html>"
