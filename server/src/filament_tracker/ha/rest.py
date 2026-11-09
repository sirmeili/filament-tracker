"""Home Assistant's REST API: fire events, and check the address and token.

Requests use a long-lived access token. The token goes only in the Authorization header
of requests to HA_URL; it is never logged, and errors never include it.
"""

import json
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from enum import StrEnum
from typing import Any
from urllib.parse import quote, urlsplit

from pydantic import SecretStr

TIMEOUT_SECONDS = 10.0
MAX_ERROR_BODY = 2000
MAX_STATES_BODY = 16 * 1024 * 1024  # every entity's state; a large install is a few MB


class Problem(StrEnum):
    UNREACHABLE = "unreachable"  # no answer: wrong address, HA down, network
    REFUSED = "refused"  # 401 or 403: the token was not accepted
    ERROR = "error"  # any other answer that is not a success


class HaRestError(Exception):
    def __init__(self, problem: Problem, status: int | None = None) -> None:
        super().__init__(problem.value if status is None else f"{problem.value} ({status})")
        self.problem = problem
        self.status = status


def parse_ha_url(url: str) -> str:
    """The address without a trailing slash. Errors never repeat it."""
    try:
        parts = urlsplit(url)
        parts.port  # noqa: B018 - raises for a bad port
    except ValueError:
        raise ValueError("HA_URL must look like http://homeassistant.local:8123") from None
    if parts.scheme not in ("http", "https"):
        raise ValueError("HA_URL must start with http:// or https://")
    if parts.username is not None or parts.password is not None:
        raise ValueError("HA_URL must not include a user name; use HA_TOKEN")
    if not parts.hostname:
        raise ValueError("HA_URL needs a host, such as http://homeassistant.local:8123")
    if parts.query or parts.fragment:
        raise ValueError("HA_URL must not have ? or #")
    return url.rstrip("/")


Opener = Callable[..., Any]


class _NoRedirects(urllib.request.HTTPRedirectHandler):
    """A redirect could send the token to another host, so none are followed: the 3xx
    answer becomes an error instead."""

    def redirect_request(self, *args: Any, **kwargs: Any) -> None:
        return None


_opener = urllib.request.build_opener(_NoRedirects)


@dataclass(frozen=True)
class HaRest:
    url: str
    token: SecretStr
    opener: Opener = _opener.open

    def __post_init__(self) -> None:
        # Only http:// and https:// addresses, checked here as well as in the settings.
        object.__setattr__(self, "url", parse_ha_url(self.url))

    def fire(self, event_type: str, data: dict[str, Any]) -> None:
        """Fire an event on Home Assistant's event bus."""
        self._request("POST", f"/api/events/{quote(event_type, safe='')}", data)

    def check(self) -> None:
        """Raise HaRestError unless the address answers and accepts the token."""
        self._request("GET", "/api/")

    def states(self) -> list[dict[str, Any]]:
        """Every entity's state, for `ft-ha check`."""
        result = self._request("GET", "/api/states", max_bytes=MAX_STATES_BODY)
        if not isinstance(result, list):
            raise HaRestError(Problem.ERROR)
        return [state for state in result if isinstance(state, dict)]

    def _request(
        self,
        method: str,
        path: str,
        body: dict[str, Any] | None = None,
        *,
        max_bytes: int = MAX_ERROR_BODY,
    ) -> Any:
        request = urllib.request.Request(  # noqa: S310 - the scheme is checked in __post_init__
            self.url + path,
            method=method,
            data=None if body is None else json.dumps(body).encode(),
            headers={
                "Authorization": f"Bearer {self.token.get_secret_value()}",
                "Content-Type": "application/json",
            },
        )
        try:
            with self.opener(request, timeout=TIMEOUT_SECONDS) as response:
                return json.loads(response.read(max_bytes) or b"null")
        except urllib.error.HTTPError as error:
            problem = Problem.REFUSED if error.code in (401, 403) else Problem.ERROR
            raise HaRestError(problem, error.code) from None
        except (urllib.error.URLError, OSError, TimeoutError):
            raise HaRestError(Problem.UNREACHABLE) from None
        except ValueError:
            # A success that is not JSON is still a success for firing an event.
            return None


def ha_rest(settings: Any) -> HaRest | None:
    """The REST client for these settings, or None unless both HA_URL and HA_TOKEN are set."""
    if not settings.ha_url or settings.ha_token is None:
        return None
    return HaRest(settings.ha_url, settings.ha_token)
