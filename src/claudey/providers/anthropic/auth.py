"""Anthropic Console connection status via the API key config."""

import os

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

    def _token_is_set(self) -> bool:
        return bool(os.getenv("ANTHROPIC_AUTH_TOKEN", "").strip())

    def is_connected(self) -> bool:
        return self._token_is_set()

    def connected_provider_ids(self) -> tuple[str, ...]:
        return (self.provider_id,) if self.is_connected() else ()

    def status(self) -> ConnectedAccountStatus:
        connected = self._token_is_set()
        state = (
            ConnectedAccountState.CONNECTED
            if connected
            else ConnectedAccountState.DISCONNECTED
        )
        return ConnectedAccountStatus(
            provider_id=self.provider_id,
            state=state,
            connected=connected,
            revision=self._revision,
        )

    async def start_login(
        self, mode: ConnectedAccountLoginMode
    ) -> ConnectedAccountStatus:
        return self.status()

    async def cancel_login(self) -> ConnectedAccountStatus:
        return self.status()

    async def disconnect(self) -> ConnectedAccountStatus:
        self._revision += 1
        return self.status()

    async def close(self) -> None:
        return None
