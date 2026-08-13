"""Shared queued-messenger bookkeeping for messaging platforms.

Owns the queue/edit-batching/delete-coalescing/timer/fire-and-forget policy
layer that is identical across platform messengers. Platform subclasses
supply the send/edit/delete primitives through abstract methods, optionally
specializing per-operation retry behavior via ``_send_via_retry`` /
``_edit_via_retry`` / ``_delete_via_retry`` (e.g. Telegram's network retry
policy) and the delete-many fallback via ``_delete_many_fallback``.
"""

from abc import ABC, abstractmethod
from collections.abc import Awaitable, Callable
from typing import Any

from ..limiter import MessagingRateLimiter
from .outbox import PlatformOutbox


class QueuedMessenger(ABC):
    """Own queued platform delivery policy shared by every platform messenger."""

    def __init__(self, *, limiter: MessagingRateLimiter) -> None:
        self._outbox = PlatformOutbox(
            limiter=limiter,
            send=self._send_queued,
            edit=self._edit_queued,
            delete_many=self._delete_many_queued,
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

    async def _send_via_retry(
        self,
        func: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Run a send primitive under the platform retry policy."""
        return await func(*args, **kwargs)

    async def _edit_via_retry(
        self,
        func: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Run an edit primitive under the platform retry policy."""
        return await func(*args, **kwargs)

    async def _delete_via_retry(
        self,
        func: Callable[..., Awaitable[Any]],
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Run a delete primitive under the platform retry policy."""
        return await func(*args, **kwargs)

    async def _delete_many_fallback(self, chat_id: str, message_ids: list[str]) -> None:
        """Delete many messages by falling back to per-message deletion."""
        for message_id in message_ids:
            await self.delete_message(chat_id, message_id)

    async def _send_queued(
        self,
        chat_id: str,
        text: str,
        reply_to: str | None,
        parse_mode: str | None,
        message_thread_id: str | None,
    ) -> str:
        """Deliver one send primitive from the outbox."""
        return await self._send_via_retry(
            self.send_message,
            chat_id,
            text,
            reply_to,
            parse_mode,
            message_thread_id,
        )

    async def _edit_queued(
        self,
        chat_id: str,
        message_id: str,
        text: str,
        parse_mode: str | None,
    ) -> None:
        """Deliver one edit primitive from the outbox."""
        await self._edit_via_retry(
            self.edit_message,
            chat_id,
            message_id,
            text,
            parse_mode,
        )

    async def _delete_many_queued(
        self,
        chat_id: str,
        message_ids: list[str],
    ) -> None:
        """Deliver one delete-many primitive from the outbox."""
        await self.delete_messages(chat_id, message_ids)

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
