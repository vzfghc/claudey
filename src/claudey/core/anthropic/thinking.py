"""Streaming parser for provider-emitted thinking tags."""

from collections.abc import Iterator
from dataclasses import dataclass
from enum import Enum


class ContentType(Enum):
    """Type of content chunk."""

    TEXT = "text"
    THINKING = "thinking"


@dataclass
class ContentChunk:
    """A chunk of parsed content."""

    type: ContentType
    content: str


class ThinkTagParser:
    """
    Streaming parser for ``<think>...</think>`` tags.

    Handles partial tags at chunk boundaries by buffering.
    """

    OPEN_TAG = "<think>"
    CLOSE_TAG = "</think>"

    def __init__(self):
        self._chunks: list[str] = []
        self._in_think_tag: bool = False

    @property
    def in_think_mode(self) -> bool:
        """Whether currently inside a think tag."""
        return self._in_think_tag

    def feed(self, content: str) -> Iterator[ContentChunk]:
        """Feed content and yield parsed chunks."""
        self._chunks.append(content)
        buffer = "".join(self._chunks)
        self._chunks = []

        while buffer:
            prev_len = len(buffer)
            if not self._in_think_tag:
                chunk, buffer = self._parse_outside_think(buffer)
            else:
                chunk, buffer = self._parse_inside_think(buffer)

            if chunk:
                yield chunk
            elif len(buffer) == prev_len:
                break

        if buffer:
            self._chunks.append(buffer)

    def _parse_outside_think(self, buffer: str) -> tuple[ContentChunk | None, str]:
        """Parse content outside think tags; return chunk and remaining buffer."""
        think_start = buffer.find(self.OPEN_TAG)
        orphan_close = buffer.find(self.CLOSE_TAG)

        if orphan_close != -1 and (think_start == -1 or orphan_close < think_start):
            pre_orphan = buffer[:orphan_close]
            buffer = buffer[orphan_close + len(self.CLOSE_TAG) :]
            if pre_orphan:
                return ContentChunk(ContentType.TEXT, pre_orphan), buffer
            return None, buffer

        if think_start == -1:
            last_bracket = buffer.rfind("<")
            if last_bracket != -1:
                potential_tag = buffer[last_bracket:]
                tag_len = len(potential_tag)
                if (
                    tag_len < len(self.OPEN_TAG)
                    and self.OPEN_TAG.startswith(potential_tag)
                ) or (
                    tag_len < len(self.CLOSE_TAG)
                    and self.CLOSE_TAG.startswith(potential_tag)
                ):
                    emit = buffer[:last_bracket]
                    buffer = buffer[last_bracket:]
                    if emit:
                        return ContentChunk(ContentType.TEXT, emit), buffer
                    return None, buffer

            emit = buffer
            buffer = ""
            if emit:
                return ContentChunk(ContentType.TEXT, emit), buffer
            return None, buffer

        pre_think = buffer[:think_start]
        buffer = buffer[think_start + len(self.OPEN_TAG) :]
        self._in_think_tag = True
        if pre_think:
            return ContentChunk(ContentType.TEXT, pre_think), buffer
        return None, buffer

    def _parse_inside_think(self, buffer: str) -> tuple[ContentChunk | None, str]:
        """Parse content inside think tags; return chunk and remaining buffer."""
        think_end = buffer.find(self.CLOSE_TAG)

        if think_end == -1:
            last_bracket = buffer.rfind("<")
            if last_bracket != -1 and len(buffer) - last_bracket < len(self.CLOSE_TAG):
                potential_tag = buffer[last_bracket:]
                if self.CLOSE_TAG.startswith(potential_tag):
                    emit = buffer[:last_bracket]
                    buffer = buffer[last_bracket:]
                    if emit:
                        return ContentChunk(ContentType.THINKING, emit), buffer
                    return None, buffer

            emit = buffer
            buffer = ""
            if emit:
                return ContentChunk(ContentType.THINKING, emit), buffer
            return None, buffer

        thinking_content = buffer[:think_end]
        buffer = buffer[think_end + len(self.CLOSE_TAG) :]
        self._in_think_tag = False
        if thinking_content:
            return ContentChunk(ContentType.THINKING, thinking_content), buffer
        return None, buffer

    def flush(self) -> ContentChunk | None:
        """Flush any remaining buffered content."""
        if self._chunks:
            chunk_type = (
                ContentType.THINKING if self._in_think_tag else ContentType.TEXT
            )
            content = "".join(self._chunks)
            self._chunks = []
            return ContentChunk(chunk_type, content)
        return None
