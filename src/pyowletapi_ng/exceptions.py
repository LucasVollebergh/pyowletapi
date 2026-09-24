class OwletError(Exception):
    """Generic exception."""


class OwletConnectionError(OwletError):
    """When a connection error occurs."""


class OwletAuthenticationError(OwletError):
    """When login details are incorrect."""


class OwletCredentialsError(OwletError):
    """When login creds are incorrect, api no longer returns if this is username or password that is incorrect."""


class OwletDevicesError(OwletError):
    """when no devices are found."""


class OwletEmailError(OwletCredentialsError):
    """When the email address is unknown or invalid.

    Accounts with email enumeration protection only return
    OwletCredentialsError, so callers should also handle the base class.
    """


class OwletPasswordError(OwletCredentialsError):
    """When the password is incorrect.

    Accounts with email enumeration protection only return
    OwletCredentialsError, so callers should also handle the base class.
    """
