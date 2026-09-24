"""Tests for the Owlet API client."""

from __future__ import annotations

import time

import aiohttp
import pytest

from pyowletapi_ng.api import OwletAPI
from pyowletapi_ng.const import REGION_INFO
from pyowletapi_ng.exceptions import (
    OwletAuthenticationError,
    OwletConnectionError,
    OwletCredentialsError,
    OwletDevicesError,
    OwletEmailError,
    OwletPasswordError,
)

from .conftest import BASE, DSN, REGION, FakeSession, load, mock_login, mock_refresh

PROPERTIES_URL = f"{BASE}/dsns/{DSN}/properties.json"
ACTIVATE_URL = f"{BASE}/dsns/{DSN}/properties/APP_ACTIVE/datapoints.json"
VERIFY_URL = (
    "https://www.googleapis.com/identitytoolkit/v3/relyingparty/verifyPassword"
    f"?key={REGION_INFO[REGION]['apiKey']}"
)


def _count(mock_api: FakeSession, method: str, url: str) -> int:
    return sum(
        len(calls)
        for (verb, called_url), calls in mock_api.requests.items()
        if verb == method and str(called_url) == url
    )


def test_invalid_region(session: FakeSession) -> None:
    with pytest.raises(OwletAuthenticationError):
        OwletAPI("mars", session=session)  # type: ignore[arg-type]


async def test_login_with_password(mock_api: FakeSession, session: FakeSession) -> None:
    mock_login(mock_api)
    api = OwletAPI(REGION, "user@example.com", "secret", session=session)
    tokens = await api.authenticate()
    assert tokens is not None
    assert tokens["api_token"] == "new_token"
    assert tokens["refresh"] == "new_refresh"
    assert api.tokens["expiry"] > time.time()


@pytest.mark.parametrize(
    ("message", "error"),
    [
        ("INVALID_PASSWORD", OwletPasswordError),
        ("EMAIL_NOT_FOUND", OwletEmailError),
        ("INVALID_EMAIL", OwletEmailError),
        ("INVALID_LOGIN_CREDENTIALS", OwletCredentialsError),
        ("TOO_MANY_ATTEMPTS_TRY_LATER : Too many attempts", OwletAuthenticationError),
        ("MISSING_PASSWORD", OwletAuthenticationError),
    ],
)
async def test_login_errors(
    mock_api: FakeSession,
    session: FakeSession,
    message: str,
    error: type[Exception],
) -> None:
    mock_api.post(VERIFY_URL, status=400, payload={"error": {"message": message}})
    api = OwletAPI(REGION, "user@example.com", "secret", session=session)
    with pytest.raises(error):
        await api.authenticate()


def test_specific_errors_are_credentials_errors() -> None:
    assert issubclass(OwletEmailError, OwletCredentialsError)
    assert issubclass(OwletPasswordError, OwletCredentialsError)


async def test_valid_token_makes_no_extra_calls(
    mock_api: FakeSession, authed_api: OwletAPI
) -> None:
    """A poll costs one activation and one properties call, no devices.json check."""
    mock_api.post(ACTIVATE_URL, payload={})
    mock_api.get(PROPERTIES_URL, payload=load("properties_v3.json"))

    response = await authed_api.get_properties(DSN)

    assert "REAL_TIME_VITALS" in response["response"]
    assert "tokens" not in response
    assert len(mock_api.requests) == 2


async def test_expired_token_is_refreshed(
    mock_api: FakeSession, session: FakeSession
) -> None:
    api = OwletAPI(
        REGION, token="old", expiry=time.time() - 10, refresh="r", session=session
    )
    mock_refresh(mock_api)
    mock_api.post(ACTIVATE_URL, payload={})
    mock_api.get(PROPERTIES_URL, payload=load("properties_v3.json"))

    response = await api.get_properties(DSN)

    assert response["tokens"]["api_token"] == "new_token"
    # Tokens are reported once, not on every following poll.
    mock_api.post(ACTIVATE_URL, payload={})
    mock_api.get(PROPERTIES_URL, payload=load("properties_v3.json"))
    assert "tokens" not in await api.get_properties(DSN)


async def test_rejected_token_is_refreshed_and_retried_once(
    mock_api: FakeSession, authed_api: OwletAPI
) -> None:
    mock_api.post(ACTIVATE_URL, status=401)
    mock_refresh(mock_api)
    mock_api.post(ACTIVATE_URL, payload={})
    mock_api.get(PROPERTIES_URL, payload=load("properties_v3.json"))

    await authed_api.get_properties(DSN)

    assert authed_api.tokens["api_token"] == "new_token"
    assert _count(mock_api, "POST", ACTIVATE_URL) == 2


async def test_rejected_twice_raises_auth_error(
    mock_api: FakeSession, authed_api: OwletAPI
) -> None:
    mock_api.post(ACTIVATE_URL, status=401)
    mock_refresh(mock_api)
    mock_api.post(ACTIVATE_URL, status=401)

    with pytest.raises(OwletAuthenticationError):
        await authed_api.get_properties(DSN)


async def test_server_error_raises_connection_error(
    mock_api: FakeSession, authed_api: OwletAPI
) -> None:
    """A 5xx no longer triggers a re-authentication loop."""
    mock_api.post(ACTIVATE_URL, status=503)
    with pytest.raises(OwletConnectionError):
        await authed_api.get_properties(DSN)
    assert len(mock_api.requests) == 1


async def test_network_error_raises_connection_error(
    mock_api: FakeSession, authed_api: OwletAPI
) -> None:
    mock_api.post(ACTIVATE_URL, exception=aiohttp.ClientConnectionError())
    with pytest.raises(OwletConnectionError):
        await authed_api.get_properties(DSN)


async def test_timeout_raises_connection_error(
    mock_api: FakeSession, authed_api: OwletAPI
) -> None:
    mock_api.post(ACTIVATE_URL, exception=TimeoutError())
    with pytest.raises(OwletConnectionError):
        await authed_api.get_properties(DSN)


async def test_activation_interval(mock_api: FakeSession, session: FakeSession) -> None:
    api = OwletAPI(
        REGION,
        token="valid_token",
        expiry=time.time() + 3600,
        refresh="r",
        session=session,
        activation_interval=60,
    )
    mock_api.post(ACTIVATE_URL, payload={})
    mock_api.get(PROPERTIES_URL, payload=load("properties_v3.json"), repeat=True)

    await api.get_properties(DSN)
    await api.get_properties(DSN)

    assert _count(mock_api, "POST", ACTIVATE_URL) == 1
    assert _count(mock_api, "GET", PROPERTIES_URL) == 2


async def test_default_activates_every_call(
    mock_api: FakeSession, authed_api: OwletAPI
) -> None:
    mock_api.post(ACTIVATE_URL, payload={}, repeat=True)
    mock_api.get(PROPERTIES_URL, payload=load("properties_v3.json"), repeat=True)

    await authed_api.get_properties(DSN)
    await authed_api.get_properties(DSN)

    assert _count(mock_api, "POST", ACTIVATE_URL) == 2


async def test_validate_authentication(
    mock_api: FakeSession, authed_api: OwletAPI
) -> None:
    mock_api.get(f"{BASE}/devices.json", status=401)
    mock_refresh(mock_api)
    tokens = await authed_api.validate_authentication()
    assert tokens is not None
    assert tokens["api_token"] == "new_token"


async def test_get_devices_filters_versions(
    mock_api: FakeSession, authed_api: OwletAPI
) -> None:
    mock_api.get(
        f"{BASE}/devices.json",
        payload=[{"device": {"dsn": DSN, "product_name": "Owlet Baby Monitors"}}],
        repeat=True,
    )
    mock_api.post(ACTIVATE_URL, payload={}, repeat=True)
    mock_api.get(PROPERTIES_URL, payload=load("properties_v3.json"), repeat=True)

    devices = await authed_api.get_devices([3])
    assert [d["device"]["dsn"] for d in devices["response"]] == [DSN]

    with pytest.raises(OwletDevicesError):
        await authed_api.get_devices([2])


async def test_get_devices_reports_refreshed_tokens(
    mock_api: FakeSession, session: FakeSession
) -> None:
    """The internal version check must not swallow the refreshed tokens."""
    api = OwletAPI(
        REGION, token="old", expiry=time.time() - 10, refresh="r", session=session
    )
    mock_refresh(mock_api)
    mock_api.get(
        f"{BASE}/devices.json", payload=[{"device": {"dsn": DSN}}], repeat=True
    )
    mock_api.post(ACTIVATE_URL, payload={}, repeat=True)
    mock_api.get(PROPERTIES_URL, payload=load("properties_v3.json"), repeat=True)

    devices = await api.get_devices()

    assert devices["tokens"]["api_token"] == "new_token"


@pytest.mark.parametrize("exception", [aiohttp.ClientConnectionError(), TimeoutError()])
async def test_login_network_error_raises_connection_error(
    mock_api: FakeSession, session: FakeSession, exception: BaseException
) -> None:
    mock_api.post(VERIFY_URL, exception=exception)
    api = OwletAPI(REGION, "user@example.com", "secret", session=session)
    with pytest.raises(OwletConnectionError):
        await api.authenticate()


async def test_refresh_network_error_raises_connection_error(
    mock_api: FakeSession, session: FakeSession
) -> None:
    api = OwletAPI(
        REGION, token="old", expiry=time.time() - 10, refresh="r", session=session
    )
    mock_api.post(
        f"https://securetoken.googleapis.com/v1/token?key={REGION_INFO[REGION]['apiKey']}",
        exception=TimeoutError(),
    )
    with pytest.raises(OwletConnectionError):
        await api.authenticate()


async def test_validate_authentication_returns_tokens_refreshed_before_check(
    mock_api: FakeSession, session: FakeSession
) -> None:
    api = OwletAPI(
        REGION, token="old", expiry=time.time() - 10, refresh="r", session=session
    )
    mock_refresh(mock_api)
    mock_api.get(f"{BASE}/devices.json", payload=[])

    tokens = await api.validate_authentication()

    assert tokens is not None
    assert tokens["api_token"] == "new_token"
