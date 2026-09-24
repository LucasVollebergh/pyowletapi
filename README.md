# pyowletapi-ng

Async Python client for the Owlet Smart Sock cloud API (Smart Sock 2, Smart Sock 3 and Dream Sock).

This is the maintained continuation of [pyowletapi](https://github.com/ryanbdclark/pyowletapi) by [Ryan Clark (@ryanbdclark)](https://github.com/ryanbdclark). Thank you, Ryan, for building it. It is used by the [Owlet Smart Sock integration for Home Assistant](https://github.com/lucasvollebergh/owlet).

> [!WARNING]
> Owlet has no public API. This library uses the same private endpoints as the Owlet app, which Owlet can change or block at any time. It is not a medical device and must not be relied on for alarms.

## Install

```bash
pip install pyowletapi-ng
```

The import package is `pyowletapi_ng`, so it can be installed next to the original `pyowletapi` without conflicts.

## Use

```python
import aiohttp

from pyowletapi_ng.api import OwletAPI
from pyowletapi_ng.sock import Sock


async def main() -> None:
    async with aiohttp.ClientSession() as session:
        api = OwletAPI("europe", "user@example.com", "password", session=session)
        await api.authenticate()

        devices = await api.get_devices()
        socks = [Sock(api, device["device"]) for device in devices["response"]]

        for sock in socks:
            result = await sock.update_properties()
            print(
                sock.serial,
                result["properties"].get("heart_rate"),
                sock.last_updated_at,
            )
```

- `region` is `"europe"` for accounts created in the EU or UK, `"world"` otherwise.
- Store `api.tokens` (access token, expiry and refresh token) and pass them back as `token`, `expiry` and `refresh` to avoid logging in with the password every time.
- `get_devices()` and `update_properties()` include a `tokens` key once after the tokens were refreshed, persist them when present.
- `Sock.last_updated_at` is the UTC time the Owlet cloud last received vitals from the sock. Use it to detect stale data.

### Options

| Argument | Default | Description |
| --- | --- | --- |
| `session` | new session | aiohttp session to use. Pass your own to share connections. |
| `timeout` | `30` | Total timeout in seconds per request. |
| `activation_interval` | `0` | Minimum seconds between two `APP_ACTIVE` requests per device. `0` activates before every request, like the original library. How long Owlet keeps a device active is not documented, so only raise this after testing with your own sock. |

### Errors

All errors derive from `OwletError`:

- `OwletCredentialsError`: login rejected. `OwletEmailError` and `OwletPasswordError` are subclasses, raised when the Owlet account still reports which part is wrong. Accounts with email enumeration protection only raise the base class.
- `OwletAuthenticationError`: tokens could not be refreshed, or the API keeps rejecting them.
- `OwletConnectionError`: network errors, timeouts and non-auth HTTP errors.
- `OwletDevicesError`: no supported sock on the account.

## Differences with pyowletapi 2025.4.x

- One poll costs one activation and one properties request. The extra `devices.json` check before every request is gone, tokens are only refreshed when they (almost) expire or are rejected.
- A rejected token (401/403) is refreshed and the request retried once, a 5xx no longer triggers a re-login loop.
- Tokens refreshed while polling are reported to the caller instead of being lost.
- Request timeouts, network errors mapped to `OwletConnectionError`.
- `OwletEmailError` and `OwletPasswordError` are back, as subclasses of `OwletCredentialsError`.
- `Sock.last_updated_at` and configurable `activation_interval`.
- Offline test suite, no Owlet account needed.

See [CHANGELOG.md](CHANGELOG.md).

## Development

```bash
pip install -e ".[test]"
ruff check . && ruff format --check .
pytest
```

## Credits

- [Ryan Clark (@ryanbdclark)](https://github.com/ryanbdclark) wrote the original [pyowletapi](https://github.com/ryanbdclark/pyowletapi). This fork builds on his work.
- API reverse engineering credited in the original project: [BastianPoe/owlet_api](https://github.com/BastianPoe/owlet_api) and [mbevand/owlet_monitor](https://github.com/mbevand/owlet_monitor).
- Maintained by [@lucasvollebergh](https://github.com/lucasvollebergh).

MIT licensed, see [LICENSE](LICENSE) and [NOTICE](NOTICE).
