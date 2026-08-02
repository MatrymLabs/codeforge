"""CARD: library -- read the Federal Guidance Library's preserved documents.

`regs` lists tracked SOURCES; the library preserves whole DOCUMENTS -- the actual
NIST/CMMC guidance, extracted to searchable text with honest freshness. This card
READS that document store; it never writes it (the library owns its own records).

Point FGL_HOME at the federal-guidance-library checkout, or clone it beside
codeforge (the default sibling). The FGL_HOME constant is read at call time, not
bound as a default, so drivers and tests can repoint it.
"""

import json
import os
from pathlib import Path
from typing import Any

FGL_HOME = Path(os.environ.get("FGL_HOME", "../federal-guidance-library"))
_DOCS_REL = Path("library/metadata/documents.json")
_TEXT_CAP = 4000  # a MUD read shouldn't flood the terminal; cap long text analogs

_NOT_MOUNTED = (
    "The guidance library is not mounted. Clone federal-guidance-library beside "
    "codeforge, or set FGL_HOME to its checkout root."
)


def _root(home: Path | None) -> Path:
    """Resolve the library root at call time (never bind FGL_HOME as a default)."""
    return home if home is not None else FGL_HOME


def _load(home: Path) -> list[dict[str, Any]]:
    """Read the document metadata store; a missing/garbled store reads as empty."""
    path = home / _DOCS_REL
    if not path.exists():
        return []
    data: Any = json.loads(path.read_text(encoding="utf-8"))
    return data if isinstance(data, list) else []


def library_index(home: Path | None = None) -> str:
    """List every preserved document (id, domain, freshness, title)."""
    docs = _load(_root(home))
    if not docs:
        return "No documents are filed in the library yet. (Ingest with FGL: `library ingest`.)"
    header = f"{'ID':32}{'DOMAIN':10}{'FRESHNESS':13}TITLE"
    lines = ["The Archive preserves these documents:", header, "-" * len(header)]
    for d in sorted(docs, key=lambda x: str(x.get("document_id", ""))):
        lines.append(
            f"{str(d.get('document_id', '?')):32}{str(d.get('domain', '?')):10}"
            f"{str(d.get('freshness_status', '?')):13}{d.get('title', '(untitled)')}"
        )
    lines.append(f"\n{len(docs)} document(s). `library <id>` to read one.")
    return "\n".join(lines)


def library_read(doc_id: str, home: Path | None = None) -> str:
    """Render one document: its dated metadata, then its text analog (capped)."""
    root = _root(home)
    docs = _load(root)
    match = next((d for d in docs if str(d.get("document_id", "")).lower() == doc_id.lower()), None)
    if match is None:
        return f"No document '{doc_id}'. Try `library` for the index."
    head = [
        f"== {match.get('title', '(untitled)')} ==",
        f"Freshness: {match.get('freshness_status') or 'unknown'} · "
        f"published: {match.get('publication_date') or 'unknown'} · "
        f"retrieved: {match.get('retrieved_date') or 'unknown'}",
        f"Source: {match.get('source_url') or '(none)'}",
        "",
    ]
    text_rel = str(match.get("text_path", ""))
    if not text_rel:
        return "\n".join([*head, "(No text analog on record for this document.)"])
    text_path = Path(text_rel)
    if not text_path.is_absolute():
        text_path = root / text_path
    if not text_path.exists():
        return "\n".join([*head, f"(Text analog missing at {text_rel}.)"])
    body = text_path.read_text(encoding="utf-8", errors="ignore")
    if len(body) > _TEXT_CAP:
        body = body[:_TEXT_CAP] + f"\n\n... (truncated; {len(body) - _TEXT_CAP} more characters)"
    return "\n".join([*head, body])


def library(arg: str = "", home: Path | None = None) -> str:
    """Dispatch: '' -> the document index; otherwise read the document with that id."""
    root = _root(home)
    if not root.exists():
        return _NOT_MOUNTED
    arg = arg.strip()
    if not arg:
        return library_index(home=root)
    return library_read(arg, home=root)
