"""Anthropic Console connection status via the API key config."""

from claudey.application.connected_accounts import (
    ConnectedAccountLoginMode,
    ConnectedAccountState,
    ConnectedAccountStatus,
)


class AnthropicAuthManager:
    """Read-only connected account that reflects the ANTHROPIC_AUTH_TOKEN config.

    There is no interactive OAuth flow — "Connect" scrolls to the key field
    in the admin form.  This lets the admin UI surface Anthropic alongside
    OpenAI in the connected-accounts strip.
    """

    provider_id = "anthropic"

    def __init__(self) -> None:
        self._revision = 0
        self._connected = False
        self._email: str | None = None

    def is_connected(self) -> bool:
        return self._connected

    def connected_provider_ids(self) -> tuple[str, ...]:
        return (self.provider_id,) if self._connected else ()

    def status(self) -> ConnectedAccountStatus:
        state = (
            ConnectedAccountState.CONNECTED
            if self._connected
            else ConnectedAccountState.DISCONNECTED
        )
        return ConnectedAccountStatus(
            provider_id=self.provider_id,
            state=state,
            connected=self._connected,
            revision=self._revision,
            email=self._email,
        )

    async def set_configured(
        self, *, configured: bool, email: str | None = None
    ) -> None:
        """Update the reflected state from the outside (called by admin)."""
        self._connected = configured
        self._email = email
        self._revision += 1

    async def start_login(
        self, mode: ConnectedAccountLoginMode
    ) -> ConnectedAccountStatus:
        return self.status()

    async def cancel_login(self) -> ConnectedAccountStatus:
        return self.status()

    async def disconnect(self) -> ConnectedAccountStatus:
        self._connected = False
        self._email = None
        self._revision += 1
        return self.status()

    async def close(self) -> None:
        return None
