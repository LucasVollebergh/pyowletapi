"""Shared fixtures for the pyowletapi-ng tests."""

from __future__ import annotations

import json
import time
from collections import defaultdict, deque
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import pytest

from pyowletapi_ng.api import OwletAPI
from pyowletapi_ng.const import REGION_INFO

FIXTURES = Path(__file__).parent / "fixtures"
REGION = "europe"
BASE = REGION_INFO[REGION]["url_base"]
DSN = "SERIAL_NUMBER"


def load(name: str) -> Any:
    """Load a JSON fixture."""
    return json.loads((FIXTURES / name).read_text())


@dataclass
class Call:
    """A recorded request."""

    kwargs: dict[str, Any]


@dataclass
class _Reply:
    status: int = 200
    payload: Any = None
    exception: BaseException | None = None
    repeat: bool = False


class _Response:
    def __init__(self, reply: _Reply) -> None:
        self.status = reply.status
        self._payload = reply.payload

    async def json(self, **_: Any) -> Any:
        return self._payload

    async def __aenter__(self) -> _Response:
        return self

    async def __aexit__(self, *_: Any) -> None:
        return None


class _RaisingContext:
    def __init__(self, exception: BaseException) -> None:
        self._exception = exception

    async def __aenter__(self) -> None:
        raise self._exception

    async def __aexit__(self, *_: Any) -> None:
        return None


@dataclass
class FakeSession:
    """Minimal stand-in for aiohttp.ClientSession with queued replies per URL."""

    replies: dict[tuple[str, str], deque[_Reply]] = field(
        default_factory=lambda: defaultdict(deque)
    )
    requests: dict[tuple[str, str], list[Call]] = field(
        default_factory=lambda: defaultdict(list)
    )

    def _add(self, method: str, url: str, **kwargs: Any) -> None:
        self.replies[(method, url)].append(_Reply(**kwargs))

    def get(self, url: str, **kwargs: Any) -> None:
        self._add("GET", url, **kwargs)

    def post(self, url: str, **kwargs: Any) -> None:
        self._add("POST", url, **kwargs)

    def request(self, method: str, url: str, **kwargs: Any) -> Any:
        key = (method, url)
        self.requests[key].append(Call(kwargs))
        queue = self.replies.get(key)
        if not queue:
            raise AssertionError(f"Unexpected request {method} {url}")
        reply = queue[0] if queue[0].repeat else queue.popleft()
        if reply.exception is not None:
            return _RaisingContext(reply.exception)
        return _Response(reply)

    async def close(self) -> None:
        return None


@pytest.fixture
def session() -> FakeSession:
    """Return a fake session, register replies with .get() and .post()."""
    return FakeSession()


@pytest.fixture
def mock_api(session: FakeSession) -> FakeSession:
    """Alias to register replies, reads better in tests."""
    return session


@pytest.fixture
def authed_api(session: FakeSession) -> OwletAPI:
    """Return an API client with a valid, non-expired token."""
    return OwletAPI(
        REGION,
        token="valid_token",
        expiry=time.time() + 3600,
        refresh="refresh_token",
        session=session,  # type: ignore[arg-type]
    )


def mock_login(mock_api: FakeSession, token: str = "new_token") -> None:
    """Mock the full password, refresh and sign in chain."""
    info = REGION_INFO[REGION]
    mock_api.post(
        f"https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword?key={info['apiKey']}",
        payload={"refreshToken": "refresh_token"},
    )
    mock_refresh(mock_api, token)


def mock_refresh(mock_api: FakeSession, token: str = "new_token") -> None:
    """Mock the refresh and sign in chain."""
    info = REGION_INFO[REGION]
    mock_api.post(
        f"https://securetoken.googleapis.com/v1/token?key={info['apiKey']}",
        payload={"refresh_token": "new_refresh", "id_token": "id_token"},
    )
    mock_api.get(info["url_mini"], payload={"mini_token": "mini"})
    mock_api.post(
        info["url_signin"], payload={"access_token": token, "expires_in": 86400}
    )
