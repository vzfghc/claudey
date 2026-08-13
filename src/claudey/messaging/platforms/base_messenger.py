"""Shared queued-messenger bookkeeping for messaging platforms.

Owns the queue/edit-batching/delete-coalescing/timer/fire-and-forget policy
layer that is identical across platform messengers. Platform subclasses supply
the send/edit/delete primitives through abstract methods and may specialize the
parse mode applied to queued sends/edits via ``_default_parse_mode``.
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable
from typing import Any

from ..limiter import MessagingRateLimiter
from .outbox import PlatformOutbox


class QueuedMessenger(ABC):
    """Own queued platform delivery policy shared by every platform messenger."""

    def __init__(self, *, limiter: MessagingRateLimiter) -> None:
        self._outbox = PlatformOutbox(
            limiter=limiter,
            send=self.send_message,
            edit=self.edit_message,
            delete_many=self.delete_messages,
        )

    @abstractmethod
    async def send_message(
        self,
        chat_id: str,
        text: str,
        reply_to: str | None = None,
        parse_mode: str | None = None,
        message_thread_id: str | None = None,
    ) -> str:
        """Send one platform message immediately and return its message id."""

    @abstractmethod
    async def edit_message(
        self,
        chat_id: str,
        message_id: str,
        text: str,
        parse_mode: str | None = None,
    ) -> None:
        """Edit one platform message immediately."""

    @abstractmethod
    async def delete_message(self, chat_id: str, message_id: str) -> None:
        """Delete one platform message immediately."""

    @abstractmethod
    async def delete_messages(self, chat_id: str, message_ids: list[str]) -> None:
        """Delete multiple platform messages best-effort."""

    def _default_parse_mode(self) -> str | None:
        """Return the parse mode applied when a queue call omits one."""
        return None

    async def queue_send_message(
        self,
        chat_id: str,
        text: str,
        reply_to: str | None = None,
        parse_mode: str | None = None,
        fire_and_forget: bool = True,
        message_thread_id: str | None = None,
    ) -> str | None:
        """Queue a platform send."""
        if parse_mode is None:
            parse_mode = self._default_parse_mode()
        return await self._outbox.queue_send_message(
            chat_id,
            text,
            reply_to,
            parse_mode,
            fire_and_forget,
            message_thread_id,
        )

    async def queue_edit_message(
        self,
        chat_id: str,
        message_id: str,
        text: str,
        parse_mode: str | None = None,
        fire_and_forget: bool = True,
    ) -> None:
        """Queue a platform edit."""
        if parse_mode is None:
            parse_mode = self._default_parse_mode()
        await self._outbox.queue_edit_message(
            chat_id,
            message_id,
            text,
            parse_mode,
            fire_and_forget,
        )

    async def queue_delete_messages(
        self,
        chat_id: str,
        message_ids: list[str],
        fire_and_forget: bool = True,
    ) -> None:
        """Queue a platform bulk delete."""
        await self._outbox.queue_delete_messages(
            chat_id,
            message_ids,
            fire_and_forget,
        )

    def fire_and_forget(self, task: Awaitable[Any]) -> None:
        """Execute a coroutine without awaiting it."""
        self._outbox.fire_and_forget(task)

    async def close(self) -> None:
        """Cancel outstanding outbound work."""
        await self._outbox.close()
