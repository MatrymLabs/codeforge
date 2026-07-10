"""CARD: dashboard -- the Lens: a read-only web view onto the forge's own evidence.

The full-stack proof. It projects REAL codeforge state -- the career board, the QualityGate
audit, the hardware store, and the latest performance run -- onto a server-rendered HTML page
plus a JSON twin. Frameless by design: stdlib `html.escape` and f-strings, no template engine
(architecture law 1: text is a projection, never a mutation). One `Snapshot` feeds both the
page and the API, so the two surfaces can never disagree. Every card fails HONEST: a source
that will not load renders a red "fail" card carrying the error, never a 500 and never a lie.

Wired into the FastAPI app (`parts/api.py`): `GET /` serves the page, `GET /api/status`
serves the same data as JSON -- the seam a future React/TypeScript front end would consume.
"""

from __future__ import annotations

import html
import re
from dataclasses import dataclass
from pathlib import Path

from fastapi import APIRouter
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

# --- the snapshot: canonical data projected to one shape ---------------------

_OK, _WATCH, _FAIL, _INFO = "ok", "watch", "fail", "info"
_BADGE = {_OK: "OK", _WATCH: "WATCH", _FAIL: "FAIL", _INFO: "INFO"}


def _root() -> Path:
    """The repo root, resolved at call time so tests can point the cards elsewhere."""
    return Path(__file__).resolve().parent.parent


@dataclass(frozen=True)
class Card:
    """One evidence card: a title, a verdict, a headline number, and detail rows."""

    key: str
    title: str
    status: str  # ok | watch | fail | info -- never color alone; paired with a text badge
    headline: str
    detail: str
    rows: tuple[tuple[str, str], ...] = ()


@dataclass(frozen=True)
class Snapshot:
    """The whole board at one instant, computed live from repo state."""

    cards: tuple[Card, ...]


def _fail_card(key: str, title: str, exc: Exception) -> Card:
    """Honest failure: a source that will not load says so, in red, with the reason."""
    return Card(key, title, _FAIL, "unavailable", f"could not load: {exc}")


def _career_card(root: Path) -> Card:
    """Skills-to-proof board: how many claims are proven, and are all of them backed?"""
    from parts.career import load_board, unproven_claims

    board = load_board()
    skills = [s for lvl in board["levels"] for s in lvl.get("skills", [])]
    counts: dict[str, int] = {}
    for s in skills:
        counts[s["status"]] = counts.get(s["status"], 0) + 1
    proven = counts.get("proven", 0)
    unbacked = unproven_claims(board, root)  # VeritasGate: every claim must cite a real artifact
    status = _FAIL if unbacked else _OK
    detail = (
        "every cited proof exists on disk"
        if not unbacked
        else f"{len(unbacked)} claim(s) cite a missing artifact"
    )
    rows = tuple((k, str(v)) for k, v in sorted(counts.items()))
    return Card("career", "Career evidence", status, f"{proven}/{len(skills)} proven", detail, rows)


def _qa_card(root: Path) -> Card:
    """QualityGate self-audit over every filed object: pass / watch / fail."""
    from parts.qualitygate import gate_all

    results = gate_all(root=root)
    tally: dict[str, int] = {}
    for r in results:
        tally[r.verdict] = tally.get(r.verdict, 0) + 1
    passed, watch, failed = tally.get("pass", 0), tally.get("watch", 0), tally.get("fail", 0)
    status = _FAIL if failed else (_WATCH if watch else _OK)
    detail = (
        "every filed object is ready"
        if status == _OK
        else f"{failed} hard gap(s), {watch} soft gap(s)"
    )
    rows = (("pass", str(passed)), ("watch", str(watch)), ("fail", str(failed)))
    return Card("qa", "QualityGate audit", status, f"{passed}/{len(results)} pass", detail, rows)


def _hardware_card(root: Path) -> Card:
    """The reusable-parts catalog: how many parts, and across how many domains."""
    from parts.hardware import load_catalog

    parts = load_catalog()
    domains = sorted({d for p in parts for d in p.reuse})
    detail = "reusable parts, each with a mirrored test twin"
    rows = (("parts", str(len(parts))), ("reuse domains", str(len(domains))))
    return Card("hardware", "Hardware store", _INFO, f"{len(parts)} parts", detail, rows)


def _perf_card(root: Path) -> Card:
    """The latest filed engine-tick benchmark, if one has been run (reports are regenerable)."""
    reports = root / "reports" / "performance"
    filed = sorted(reports.glob("*.md")) if reports.is_dir() else []
    if not filed:
        return Card("perf", "Performance", _INFO, "not yet run", "run `make bench` to file one")
    latest = filed[-1]
    text = latest.read_text(encoding="utf-8")
    throughput = re.search(r"throughput\s*:\s*([\d,]+)", text)
    median = re.search(r"median\s*([\d.]+)us", text)
    headline = f"{throughput.group(1)} cmd/s" if throughput else "recorded"
    detail = f"median {median.group(1)}us  ({latest.stem})" if median else latest.stem
    return Card("perf", "Performance", _OK, headline, detail)


# Ordered builders; each is cordoned so one bad source cannot blank the board.
_BUILDERS: tuple[tuple[str, str, object], ...] = (
    ("career", "Career evidence", _career_card),
    ("qa", "QualityGate audit", _qa_card),
    ("hardware", "Hardware store", _hardware_card),
    ("perf", "Performance", _perf_card),
)


def build_snapshot(root: Path | None = None) -> Snapshot:
    """Read every source once and project it to cards. Failures render honest, not fatal."""
    base = root if root is not None else _root()
    cards: list[Card] = []
    for key, title, builder in _BUILDERS:
        try:
            cards.append(builder(base))  # type: ignore[operator]
        except Exception as exc:  # a dashboard must never 500; it must tell the truth instead
            cards.append(_fail_card(key, title, exc))
    return Snapshot(tuple(cards))


# --- JSON twin: a TYPED contract the front end consumes ----------------------
#
# Explicit Pydantic response models, so FastAPI documents the shape in OpenAPI (/docs) and
# a future React/TypeScript client can generate types from it. The page and this contract
# are fed by the same Snapshot, so they can never disagree.


class StatusCard(BaseModel):
    """One evidence card in the JSON status contract."""

    key: str
    title: str
    status: str
    headline: str
    detail: str
    rows: dict[str, str]


class StatusPayload(BaseModel):
    """The read-only status contract served at GET /api/status."""

    engine: str
    cards: list[StatusCard]


def status_payload(snapshot: Snapshot) -> StatusPayload:
    """The machine-readable projection: the same data the page renders, typed."""
    return StatusPayload(
        engine="codeforge",
        cards=[
            StatusCard(
                key=c.key,
                title=c.title,
                status=c.status,
                headline=c.headline,
                detail=c.detail,
                rows={label: value for label, value in c.rows},
            )
            for c in snapshot.cards
        ],
    )


# --- HTML projection: semantic, responsive, accessible, frameless ------------

_STYLE = """
:root { color-scheme: light dark; --ok:#1a7f37; --watch:#9a6700; --fail:#b42318; --info:#0b5cad;
  --bg:#0d1117; --panel:#161b22; --edge:#30363d; --ink:#e6edf3; --muted:#8b949e; }
* { box-sizing: border-box; }
body { margin:0; font:16px/1.5 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  background:var(--bg); color:var(--ink); }
a.skip { position:absolute; left:-999px; }
a.skip:focus { left:1rem; top:1rem; background:var(--panel); padding:.5rem 1rem; z-index:2; }
header { border-bottom:1px solid var(--edge); padding:1.5rem 1rem; }
header h1 { margin:0 0 .25rem; font-size:1.5rem; }
header p { margin:0; color:var(--muted); }
nav { padding:.5rem 1rem; border-bottom:1px solid var(--edge); }
nav a { color:var(--info); margin-right:1rem; text-decoration:none; }
nav a:hover, nav a:focus-visible { text-decoration:underline; }
main { padding:1.5rem 1rem; max-width:1000px; margin:0 auto; }
.grid { display:grid; gap:1rem; grid-template-columns:repeat(auto-fit,minmax(240px,1fr)); }
article.card { background:var(--panel); border:1px solid var(--edge); border-radius:10px;
  padding:1.1rem; display:flex; flex-direction:column; gap:.4rem; }
.card h2 { margin:0; font-size:1rem; color:var(--muted); font-weight:600; }
.headline { font-size:1.9rem; font-weight:700; letter-spacing:-.02em; }
.detail { color:var(--muted); font-size:.9rem; }
.badge { align-self:flex-start; font-size:.72rem; font-weight:700; letter-spacing:.06em;
  padding:.15rem .5rem; border-radius:999px; border:1px solid currentColor; }
.badge.ok{color:var(--ok);} .badge.watch{color:var(--watch);}
.badge.fail{color:var(--fail);} .badge.info{color:var(--info);}
dl.rows { margin:.3rem 0 0; display:grid; grid-template-columns:1fr auto; gap:.15rem .75rem;
  font-size:.85rem; }
dl.rows dt { color:var(--muted); }
dl.rows dd { margin:0; text-align:right; font-variant-numeric:tabular-nums; }
:focus-visible { outline:2px solid var(--info); outline-offset:2px; }
footer { border-top:1px solid var(--edge); padding:1.25rem 1rem; color:var(--muted);
  font-size:.85rem; text-align:center; }
footer a { color:var(--info); }
""".strip()


def _card_html(card: Card) -> str:
    esc = html.escape
    rows = ""
    if card.rows:
        pairs = "".join(f"<dt>{esc(k)}</dt><dd>{esc(v)}</dd>" for k, v in card.rows)
        rows = f'<dl class="rows">{pairs}</dl>'
    heading_id = f"card-{esc(card.key)}"
    return (
        f'<article class="card" aria-labelledby="{heading_id}">'
        f'<h2 id="{heading_id}">{esc(card.title)}</h2>'
        f'<span class="badge {esc(card.status)}">{_BADGE.get(card.status, "?")}</span>'
        f'<p class="headline">{esc(card.headline)}</p>'
        f'<p class="detail">{esc(card.detail)}</p>'
        f"{rows}"
        f"</article>"
    )


def render_page(snapshot: Snapshot) -> str:
    """Project the snapshot to one accessible, responsive HTML document (no framework)."""
    cards = "".join(_card_html(c) for c in snapshot.cards)
    return (
        "<!doctype html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        "<title>CodeForge readiness dashboard</title>"
        f"<style>{_STYLE}</style>"
        "</head>"
        "<body>"
        '<a class="skip" href="#board">Skip to the board</a>'
        "<header>"
        "<h1>CodeForge readiness</h1>"
        "<p>A live, read-only Lens onto the forge's own evidence. Computed from repo state.</p>"
        "</header>"
        '<nav aria-label="Surfaces">'
        '<a href="/api/status">JSON status</a>'
        '<a href="/docs">API docs</a>'
        '<a href="/health">Health</a>'
        "</nav>"
        '<main><section id="board" aria-label="Readiness board">'
        f'<div class="grid">{cards}</div>'
        "</section></main>"
        "<footer>"
        "Server-rendered by FastAPI, no front-end framework. "
        'The same data is served as JSON at <a href="/api/status">/api/status</a>.'
        "</footer>"
        "</body></html>"
    )


# --- the routes: two thin callers, mounted on the FastAPI app ----------------

router = APIRouter()


@router.get("/", response_class=HTMLResponse)
def dashboard_page() -> str:
    """The portfolio landing page: the readiness board, server-rendered."""
    return render_page(build_snapshot())


@router.get("/api/status", response_model=StatusPayload)
def dashboard_status() -> StatusPayload:
    """The read-only, typed JSON twin -- the seam a React/TypeScript front end would consume.
    Typed with StatusPayload, so the contract is documented in OpenAPI at /docs."""
    return status_payload(build_snapshot())
