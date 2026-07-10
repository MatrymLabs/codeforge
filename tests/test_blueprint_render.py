"""Test twin for parts/blueprint_render.py -- the static HTML projection.

Acceptance: a Blueprint renders to a semantic, accessible HTML document carrying its real
content, and files to reports/blueprints/. Refusal: hostile Blueprint text is HTML-escaped,
never injected.
"""

from parts.blueprint import from_dict
from parts.blueprint_render import render_html, write_html

_BP = from_dict(
    {
        "blueprint_id": "render_me",
        "title": "Render Me",
        "intent": "A plan to prove the renderer.",
        "requirements": ["Show the requirements.", "Show the tasks."],
        "tasks": ["Draw the page."],
        "stack": {"engine": "custom Python"},
    }
)


def test_render_is_a_semantic_accessible_document():
    page = render_html(_BP)
    assert page.startswith("<!doctype html>")
    for token in ('<html lang="en">', "<main>", "viewport", "<footer>", "aria-labelledby"):
        assert token in page


def test_render_shows_the_real_content():
    page = render_html(_BP)
    assert "Render Me" in page
    assert "Show the requirements." in page
    assert "Draw the page." in page
    assert "custom Python" in page


def test_render_labels_the_status():
    assert "DRAFT" in render_html(_BP)


def test_hostile_text_is_escaped():
    evil = from_dict(
        {
            "blueprint_id": "evil",
            "title": "<script>alert(1)</script>",
            "intent": "x",
            "requirements": ["<img src=x onerror=alert(1)>"],
        }
    )
    page = render_html(evil)
    assert "<script>alert(1)</script>" not in page
    assert "&lt;script&gt;" in page
    assert "<img src=x" not in page


def test_write_html_files_to_reports(tmp_path):
    path = write_html(_BP, root=tmp_path)
    assert path == tmp_path / "reports" / "blueprints" / "render_me.html"
    assert path.read_text().startswith("<!doctype html>")
