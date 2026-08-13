"""Discord outbound delivery."""

from collections.abc import Callable
from typing import Any, cast

from ..limiter import MessagingRateLimiter
from .base_messenger import QueuedMessenger

DISCORD_MESSAGE_LIMIT = 2000

ClientGetter = Callable[[], Any]
DiscordGetter = Callable[[], Any]


def truncate_discord_message(text: str, limit: int = DISCORD_MESSAGE_LIMIT) -> str:
    """Return text that fits Discord's message limit."""
    if len(text) <= limit:
        return text
    return text[: limit - 3] + "..."


class DiscordMessenger(QueuedMessenger):
    """Owns Discord sends, edits, deletes, and queued delivery."""

    def __init__(
        self,
        *,
        get_client: ClientGetter,
        get_discord: DiscordGetter,
        limiter: MessagingRateLimiter,
    ) -> None:
        self._get_client = get_client
        self._get_discord = get_discord
        super().__init__(limiter=limiter)

    async def send_message(
        self,
        chat_id: str,
        text: str,
        reply_to: str | None = None,
        parse_mode: str | None = None,
        message_thread_id: str | None = None,
    ) -> str:
        """Send a Discord message immediately."""
        client = self._get_client()
        channel = client.get_channel(int(chat_id))
        if not channel or not hasattr(channel, "send"):
            raise RuntimeError(f"Channel {chat_id} not found")

        text = truncate_discord_message(text)
        channel = cast(Any, channel)

        if reply_to:
            discord = self._get_discord()
            ref = discord.MessageReference(
                message_id=int(reply_to),
                channel_id=int(chat_id),
            )
            msg = await channel.send(content=text, reference=ref)
        else:
            msg = await channel.send(content=text)

        return str(msg.id)

    async def edit_message(
        self,
        chat_id: str,
        message_id: str,
        text: str,
        parse_mode: str | None = None,
    ) -> None:
        """Edit a Discord message immediately."""
        client = self._get_client()
        channel = client.get_channel(int(chat_id))
        if not channel or not hasattr(channel, "fetch_message"):
            raise RuntimeError(f"Channel {chat_id} not found")

        discord = self._get_discord()
        channel = cast(Any, channel)
        try:
            msg = await channel.fetch_message(int(message_id))
        except discord.NotFound:
            return

        await msg.edit(content=truncate_discord_message(text))

    async def delete_message(self, chat_id: str, message_id: str) -> None:
        """Delete a Discord message immediately."""
        client = self._get_client()
        channel = client.get_channel(int(chat_id))
        if not channel or not hasattr(channel, "fetch_message"):
            return

        discord = self._get_discord()
        channel = cast(Any, channel)
        try:
            msg = await channel.fetch_message(int(message_id))
            await msg.delete()
        except discord.NotFound, discord.Forbidden:
            pass

    async def delete_messages(self, chat_id: str, message_ids: list[str]) -> None:
        """Delete multiple Discord messages best-effort."""
        for mid in message_ids:
            await self.delete_message(chat_id, mid)
