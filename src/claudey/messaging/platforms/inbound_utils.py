"""Shared inbound normalization helpers for messaging platforms."""

from loguru import logger


def log_incoming_text_message(
    *,
    platform_label: str,
    chat_id: str,
    message_id: str,
    reply_to: str | None,
    raw_content: str,
    log_raw_messaging_content: bool,
) -> None:
    """Log an inbound text message with a preview or its raw length."""
    if log_raw_messaging_content:
        text_preview = "".join([raw_content[:80], "..."])[:80]
        logger.info(
            "{}_MSG: chat_id={} message_id={} reply_to={} text_preview={!r}",
            platform_label,
            chat_id,
            message_id,
            reply_to,
            text_preview,
        )
    else:
        logger.info(
            "{}_MSG: chat_id={} message_id={} reply_to={} text_len={}",
            platform_label,
            chat_id,
            message_id,
            reply_to,
            len(raw_content),
        )
