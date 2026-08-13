"""Shared markdown-it inline token walker for messaging renderers."""

from collections.abc import Callable, Sequence
from dataclasses import dataclass

from markdown_it.token import Token


@dataclass(frozen=True, slots=True)
class InlineRenderProfile:
    """Platform-specific inline markdown emission rules."""

    escape_text: Callable[[str], str]
    escape_code: Callable[[str], str]
    escape_url: Callable[[str], str]
    emphasis: str
    strong: str
    strikethrough: str


def render_inline_tokens(
    children: Sequence[Token], profile: InlineRenderProfile
) -> str:
    """Walk inline tokens using platform-specific escaping and delimiters."""
    output: list[str] = []
    index = 0
    while index < len(children):
        token = children[index]
        if token.type == "link_open":
            link, index = _render_link(children, index, profile)
            output.append(link)
        else:
            output.append(_render_token(token, profile))
        index = index + 1
    return "".join(output)


def _render_link(
    children: Sequence[Token], index: int, profile: InlineRenderProfile
) -> tuple[str, int]:
    token = children[index]
    href = _string_attr(token, "href")
    inner_tokens: list[Token] = []
    link_index = index + 1
    while link_index < len(children) and children[link_index].type != "link_close":
        inner_tokens.append(children[link_index])
        link_index = link_index + 1
    text = "".join(
        child.content for child in inner_tokens if child.type in {"text", "code_inline"}
    )
    return f"[{profile.escape_text(text)}]({profile.escape_url(href)})", link_index


def _render_token(token: Token, profile: InlineRenderProfile) -> str:
    token_type = token.type
    if token_type == "text":
        return profile.escape_text(token.content)
    if token_type in {"softbreak", "hardbreak"}:
        return "\n"
    if token_type in {"em_open", "em_close"}:
        return profile.emphasis
    if token_type in {"strong_open", "strong_close"}:
        return profile.strong
    if token_type in {"s_open", "s_close"}:
        return profile.strikethrough
    if token_type == "code_inline":
        return f"`{profile.escape_code(token.content)}`"
    if token_type == "image":
        return _render_image(token, profile)
    return profile.escape_text(token.content or "")


def _render_image(token: Token, profile: InlineRenderProfile) -> str:
    href = _string_attr(token, "src")
    alt = token.content or ""
    if alt:
        return f"{profile.escape_text(alt)} ({profile.escape_url(href)})"
    return profile.escape_url(href)


def _string_attr(token: Token, name: str) -> str:
    value = token.attrGet(name)
    return value if isinstance(value, str) else ""
