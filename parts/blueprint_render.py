"""CARD: blueprint_render -- project a Blueprint to a static HTML/CSS page.

The renderer spine of the forge: a Blueprint (data) becomes a self-contained, accessible
HTML page (a projection). Frameless, same as the dashboard: stdlib `html.escape` + f-strings,
inline CSS, no template engine and no new dependency. It never mutates the Blueprint; it only
reads. Rendered pages are regenerable evidence, filed under reports/blueprints/ (git-ignored),
so the JSON record stays the single source of truth.
"""

from __future__ import annotations

import html
from pathlib import Path

from parts.blueprint import Blueprint

_STYLE = """
:root { color-scheme: light dark; --bg:#0d1117; --panel:#161b22; --edge:#30363d;
  --ink:#e6edf3; --muted:#8b949e; --accent:#0b5cad; }
* { box-sizing:border-box; }
body { margin:0; font:16px/1.6 system-ui,-apple-system,Segoe UI,Roboto,sans-serif;
  background:var(--bg); color:var(--ink); }
main { max-width:760px; margin:0 auto; padding:2rem 1.25rem; }
h1 { margin:0 0 .25rem; letter-spacing:-.02em; }
.intent { color:var(--muted); font-size:1.05rem; margin:0 0 1rem; }
.meta { display:flex; gap:.5rem; flex-wrap:wrap; margin-bottom:1.5rem; }
.chip { font-size:.75rem; border:1px solid var(--edge); border-radius:999px;
  padding:.2rem .6rem; color:var(--muted); }
.chip.status { color:var(--accent); border-color:currentColor; font-weight:700;
  letter-spacing:.05em; }
section { background:var(--panel); border:1px solid var(--edge); border-radius:10px;
  padding:1rem 1.25rem; margin-bottom:1rem; }
section h2 { margin:0 0 .5rem; font-size:1rem; color:var(--muted); }
ol, ul { margin:.25rem 0; padding-left:1.25rem; }
li { margin:.2rem 0; }
dl.stack { display:grid; grid-template-columns:auto 1fr; gap:.25rem .75rem; margin:.25rem 0; }
dl.stack dt { color:var(--muted); font-weight:600; }
dl.stack dd { margin:0; }
:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
footer { color:var(--muted); font-size:.8rem; text-align:center; padding:1rem; }
""".strip()


def render_html(bp: Blueprint) -> str:
    """Project one Blueprint to a self-contained, accessible HTML document (no framework)."""
    esc = html.escape
    reqs = "".join(f"<li>{esc(r)}</li>" for r in bp.requirements)
    body = [
        '<section aria-labelledby="req-h">',
        '<h2 id="req-h">Requirements</h2>',
        f"<ol>{reqs}</ol>",
        "</section>",
    ]
    sec = "".join(f"<li>{esc(s)}</li>" for s in bp.security)
    body += [
        '<section aria-labelledby="sec-h">',
        '<h2 id="sec-h">Security</h2>',
        f"<ul>{sec}</ul>",
        "</section>",
    ]
    if bp.tasks:
        tasks = "".join(f"<li>{esc(t)}</li>" for t in bp.tasks)
        body += [
            '<section aria-labelledby="task-h">',
            '<h2 id="task-h">Tasks</h2>',
            f"<ul>{tasks}</ul>",
            "</section>",
        ]
    if bp.stack:
        rows = "".join(f"<dt>{esc(layer)}</dt><dd>{esc(choice)}</dd>" for layer, choice in bp.stack)
        body += [
            '<section aria-labelledby="stack-h">',
            '<h2 id="stack-h">Stack</h2>',
            f'<dl class="stack">{rows}</dl>',
            "</section>",
        ]
    return (
        "<!doctype html>"
        '<html lang="en">'
        "<head>"
        '<meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        f"<title>Blueprint: {esc(bp.title)}</title>"
        f"<style>{_STYLE}</style>"
        "</head>"
        "<body><main>"
        f"<h1>{esc(bp.title)}</h1>"
        f'<p class="intent">{esc(bp.intent)}</p>'
        '<div class="meta">'
        f'<span class="chip">id: {esc(bp.blueprint_id)}</span>'
        f'<span class="chip status">{esc(bp.status.upper())}</span>'
        "</div>"
        f"{''.join(body)}"
        "</main>"
        "<footer>Forged by CodeForge, rendered frameless "
        "(stdlib HTML, no template engine).</footer>"
        "</body></html>"
    )


def render_fragment(bp: Blueprint) -> str:
    """A self-contained HTML fragment (no <html>/<head>/<style>) for embedding via HTMX.
    Styling comes from the host page (it reuses the dashboard's CSS classes). Hostile text
    is escaped, same as the full page."""
    esc = html.escape
    out = [
        f"<h2>{esc(bp.title)}</h2>",
        f'<p class="bp-intent">{esc(bp.intent)}</p>',
        "<h3>Requirements</h3>",
        "<ol>" + "".join(f"<li>{esc(r)}</li>" for r in bp.requirements) + "</ol>",
        "<h3>Security</h3>",
        "<ul>" + "".join(f"<li>{esc(s)}</li>" for s in bp.security) + "</ul>",
    ]
    if bp.tasks:
        out.append("<h3>Tasks</h3>")
        out.append("<ul>" + "".join(f"<li>{esc(t)}</li>" for t in bp.tasks) + "</ul>")
    if bp.stack:
        rows = "".join(f"<dt>{esc(layer)}</dt><dd>{esc(choice)}</dd>" for layer, choice in bp.stack)
        out.append(f'<h3>Stack</h3><dl class="rows">{rows}</dl>')
    return "".join(out)


def write_html(bp: Blueprint, root: Path | None = None) -> Path:
    """File the rendered page as regenerable evidence under reports/blueprints/."""
    base = (
        (root if root is not None else Path(__file__).resolve().parent.parent)
        / "reports"
        / "blueprints"
    )
    base.mkdir(parents=True, exist_ok=True)
    path = base / f"{bp.blueprint_id}.html"
    path.write_text(render_html(bp), encoding="utf-8")
    return path
