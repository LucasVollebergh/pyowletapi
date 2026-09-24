"""Tests for the Sock model."""

from __future__ import annotations

import datetime

import pytest

from pyowletapi_ng.api import OwletAPI
from pyowletapi_ng.sock import Sock

from .conftest import BASE, DSN, FakeSession, load

PROPERTIES_URL = f"{BASE}/dsns/{DSN}/properties.json"
ACTIVATE_URL = f"{BASE}/dsns/{DSN}/properties/APP_ACTIVE/datapoints.json"
COMMAND_URL = f"{BASE}/dsns/{DSN}/properties/BASE_STATION_ON_CMD/datapoints.json"


@pytest.fixture
def sock(authed_api: OwletAPI) -> Sock:
    return Sock(authed_api, {"dsn": DSN, "product_name": "Owlet Baby Monitors"})


async def test_v3_properties(mock_api: FakeSession, sock: Sock) -> None:
    mock_api.post(ACTIVATE_URL, payload={})
    mock_api.get(PROPERTIES_URL, payload=load("properties_v3.json"))

    await sock.update_properties()

    assert sock.version == 3
    assert sock.properties["heart_rate"] == 97.0
    assert sock.properties["oxygen_saturation"] == 99.0
    assert sock.properties["sleep_state"] == 8
    assert sock.last_updated_at == datetime.datetime(
        2023, 5, 24, 14, 15, 50, tzinfo=datetime.UTC
    )


async def test_v2_properties(mock_api: FakeSession, sock: Sock) -> None:
    mock_api.post(ACTIVATE_URL, payload={})
    mock_api.get(PROPERTIES_URL, payload=load("properties_v2.json"))

    await sock.update_properties()

    assert sock.version == 2
    assert sock.properties["heart_rate"] == 145
    # Newest vital timestamp in the fixture is HEART_RATE / MOVEMENT at 14:05:01.
    assert sock.last_updated_at == datetime.datetime(
        2023, 11, 20, 14, 5, 1, tzinfo=datetime.UTC
    )


def test_last_updated_without_data(sock: Sock) -> None:
    assert sock.last_updated_at is None


async def test_control_base_station(mock_api: FakeSession, sock: Sock) -> None:
    mock_api.post(ACTIVATE_URL, payload={})
    mock_api.post(COMMAND_URL, payload={"datapoint": {}})

    assert await sock.control_base_station(False) is True
    body = next(
        call.kwargs["json"]
        for (verb, url), calls in mock_api.requests.items()
        if str(url) == COMMAND_URL
        for call in calls
    )
    assert '"val": "false"' in body["datapoint"]["value"]
