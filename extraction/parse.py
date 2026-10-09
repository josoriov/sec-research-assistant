"""Heading-aware HTML extraction for SEC filings.

Turns a raw 10-K/10-K-A HTML document into bounded, source-linked passages.
The extraction walks block elements in document order, tracks the nearest
"Item N." / "PART N" heading as the section, renders whole tables as row text,
and groups consecutive blocks up to a character bound.

Known limitation: text that lives directly inside a container element which also
holds nested block elements (mixed content) is not emitted, because only leaf
blocks are visited. SEC documents render their prose in leaf <div>/<table>
blocks, so coverage is high; this is documented in docs/setup.md.
"""
from __future__ import annotations

import hashlib
import re

from bs4 import BeautifulSoup

from extraction import PROCESSING_VERSION

PASSAGE_MAX_CHARS = 1500

# Match "Item 7." / "Item 7A." / "Part II" (case-insensitive). The heading must
# also be short, so a sentence that merely starts with "Item 7" is not a heading.
_HEADING_RE = re.compile(r"(?i)^(item\s*\d+[a-z]?\b|part\s+[ivx]+\b)")
_BLOCK_TAGS = ("div", "table", "p", "li", "h1", "h2", "h3", "h4", "h5", "h6", "section")
_WHITESPACE = re.compile(r"\s+")
_MAX_HEADING_CHARS = 200


def _clean(text: str) -> str:
    return _WHITESPACE.sub(" ", text).strip()


def passage_hash(processing_version: str, section: str | None, text: str) -> str:
    """Content-addressed passage hash: content, section, and processing version."""
    return hashlib.sha256(
        f"{processing_version}\n{section or ''}\n{text}".encode()
    ).hexdigest()


def _heading(text: str) -> str | None:
    if len(text) > _MAX_HEADING_CHARS:
        return None
    return text if _HEADING_RE.match(text) else None


def _table_text(table) -> str:
    """Render a table as row text, preserving empty-cell positions.

    Only rows owned by this table are enumerated, so a nested table's text is
    emitted once (through its containing cell) rather than twice.
    """
    rows = []
    for tr in table.find_all("tr"):
        if tr.find_parent("table") is not table:
            continue
        cells = [_clean(cell.get_text(" ", strip=True))
                 for cell in tr.find_all(["td", "th"], recursive=False)]
        if any(cells):
            rows.append(" | ".join(cells))
    return _clean(" ; ".join(rows))


def _leaf_blocks(soup):
    """Yield block text in document order.

    A table is always rendered whole (even when its cells contain block
    elements), and its descendants are never emitted separately, so labels and
    row/cell boundaries survive. Non-table block elements are emitted only when
    they contain no nested block; otherwise their own leaf descendants are.
    """
    inside_table = set()
    for table in soup.find_all("table"):
        for descendant in table.find_all(True):
            inside_table.add(id(descendant))
    for element in soup.find_all(_BLOCK_TAGS):
        if id(element) in inside_table:
            continue
        if element.name == "table":
            text = _table_text(element)
        else:
            if element.find(_BLOCK_TAGS):
                continue
            text = _clean(element.get_text(" ", strip=True))
        if text:
            yield text


def _split(text: str, max_chars: int) -> list[str]:
    """Split text into <= max_chars chunks, preferring whitespace boundaries."""
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        if end < len(text):
            space = text.rfind(" ", start, end)
            if space > start:
                end = space
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        start = end
    return chunks


def extract_blocks(html: bytes | str, processing_version: str = PROCESSING_VERSION,
                   max_chars: int = PASSAGE_MAX_CHARS) -> list[dict]:
    """Return bounded passages from filing HTML, in document order."""
    soup = BeautifulSoup(html, "html.parser")
    for tag in soup(["script", "style"]):
        tag.decompose()

    blocks: list[dict] = []
    section: str | None = None
    heading: str | None = None
    buffer: list[str] = []

    def buffer_size() -> int:
        # Include the single space inserted between buffered chunks on flush.
        return sum(len(chunk) for chunk in buffer) + max(0, len(buffer) - 1)

    def flush() -> None:
        nonlocal buffer
        text = _clean(" ".join(buffer))
        buffer = []
        if text:
            blocks.append({
                "block_ordinal": len(blocks),
                "section": section,
                "heading": heading,
                "text": text,
                "block_hash": passage_hash(processing_version, section, text),
            })

    def append(chunk: str) -> None:
        if not chunk:
            return
        if buffer and buffer_size() + 1 + len(chunk) > max_chars:
            flush()
        buffer.append(chunk)

    for text in _leaf_blocks(soup):
        if not text:
            continue
        found = _heading(text)
        if found:
            flush()
            section = found
            heading = found
            for chunk in _split(found, max_chars):
                append(chunk)
            continue
        for chunk in _split(text, max_chars):
            append(chunk)
    flush()
    return blocks
