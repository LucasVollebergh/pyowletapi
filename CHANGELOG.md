# Changelog

## 2026.9.0 (2026-09-24)

First release as `pyowletapi-ng`, the maintained continuation of [pyowletapi](https://github.com/ryanbdclark/pyowletapi) by Ryan Clark. Earlier versions were released as `pyowletapi`.

### Breaking
- Distribution renamed to `pyowletapi-ng`, import package renamed to `pyowletapi_ng`.
- Python 3.12 or newer.

### Fix
- Tokens refreshed while polling are reported by `get_devices()`, `get_properties()` and `validate_authentication()` instead of being lost.
- Network errors and timeouts while logging in or refreshing tokens raise `OwletConnectionError` instead of raw aiohttp errors.
- `get_properties()` no longer crashes on an empty property list and reports refreshed tokens only once.
- No re-login loop on 5xx responses, rejected tokens are refreshed and the request retried once.
- The identitytoolkit error pattern for missing email/password or an invalid API key now matches.
- `get_devices()` no longer uses a mutable default argument.

### Feature
- `OwletEmailError` and `OwletPasswordError` are back, as subclasses of `OwletCredentialsError`.
- Fewer API calls per poll: no `devices.json` check before every request.
- `timeout` and `activation_interval` options on `OwletAPI`.
- `Sock.last_updated_at` with the UTC time of the latest vitals.
- Network errors and timeouts raise `OwletConnectionError`.
- Offline test suite, CI and PyPI publishing via Trusted Publishing.
