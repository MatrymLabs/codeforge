"""CARD: web_api_generator -- generate a small, runnable WEB API from a validated ProjectModel,
record it as an artifact (checksums + provenance), and validate it by running it.

The SECOND target generator (after `cli_generator`, Stage 6): the proof the platform's generation
pipeline GENERALIZES beyond one target family, which is what lets CodeForge honestly claim target
generation at all ("no universal generation until tested generators exist"). Given a `ProjectModel`
(Stage 4), `generate_web_api` emits a small but genuinely runnable Python web service:

  * a package (`<slug>/__init__.py` + `<slug>/app.py`) whose `build_app()` returns a pure WSGI
    callable -- routes are `/` (service card), `/health`, and one `/<action>` per model action (or a
    default `/info`); every response is JSON. `serve(port)` runs it on `wsgiref` (stdlib, no
    framework dependency, so the generated target installs and runs anywhere Python does);
  * a `<slug>/__main__.py` CLI: `--check` (build the app + list routes, DO NOT bind a port),
    `--serve [PORT]`, `--version`;
  * a generated test (`tests/test_api.py`) that calls the WSGI app DIRECTLY (no socket) + a
    `conftest.py`, plus a `pyproject.toml` (console-script entry point) and a `README.md`.

Output is **reproducible** (no timestamps, so the same model yields identical files + checksums),
each file is **checksummed** (sha256), and the artifact carries the model's **provenance**.
`validate_runs` proves it RUNS (`python -m <pkg> --check`, exit 0, no network) and `validate_tests`
proves its tests PASS -- both through the Stage-5 `tool_runner`, so the slice closes on itself.
Reuses `cli_generator`'s artifact record + helpers (no duplication). No `kernel/world/` coupling.
Status: PROTOTYPED (see docs/seed_platform/RECENTERING.md).
"""

from __future__ import annotations

import json
import re
import shutil
import sys
from pathlib import Path

from kernel.seedlab.cli_generator import (
    GeneratedArtifact,
    GeneratorError,
    _package_name,
    _sha256,
    _target_source,
)
from kernel.seedlab.project_model import ProjectModel
from kernel.seedlab.tool_runner import ToolRunResult, run_tool

_SLUG = re.compile(r"[^a-z0-9]+")


def _routes(model: ProjectModel) -> list[str]:
    """The API's action-routes, slugged from the model's actions (a default `info` when none).
    Dedupes preserving order and never exposes `health` (reserved for the health check)."""
    seen: set[str] = {"health"}
    ordered: list[str] = []
    for action in model.actions:
        route = _SLUG.sub("_", action.lower()).strip("_")
        if route and route not in seen:
            seen.add(route)
            ordered.append(route)
    return ordered or ["info"]


# The WSGI app + server body: PLAIN text (its dict-braces are literal), so no f-string escaping.
# It reads the SERVICE/ROUTES/__version__ globals the header injects, keeping model values out of
# the logic and the logic reproducible.
_APP_BODY = '''

def build_app():
    """Return a WSGI application. Pure and importable, so tests call it with no socket."""

    def app(environ, start_response):
        path = environ.get("PATH_INFO", "/").strip("/")
        if path == "":
            body, code = {"service": SERVICE, "routes": ROUTES, "version": __version__}, "200 OK"
        elif path == "health":
            body, code = {"status": "ok"}, "200 OK"
        elif path in ROUTES:
            body, code = {"route": path, "ok": True}, "200 OK"
        else:
            body, code = {"error": "not found", "path": path}, "404 Not Found"
        payload = json.dumps(body).encode("utf-8")
        start_response(
            code,
            [("Content-Type", "application/json"), ("Content-Length", str(len(payload)))],
        )
        return [payload]

    return app


def serve(port=8000):
    """Run the API on the stdlib wsgiref server (localhost). Blocks until interrupted."""
    from wsgiref.simple_server import make_server

    with make_server("127.0.0.1", port, build_app()) as httpd:
        print(f"serving on http://127.0.0.1:{port}")
        httpd.serve_forever()
'''

_MAIN_BODY = """

def main(argv=None):
    parser = argparse.ArgumentParser(prog=PROG, description=SERVICE)
    parser.add_argument("--version", action="version", version=__version__)
    parser.add_argument(
        "--check", action="store_true", help="build the app and list routes; do not serve"
    )
    parser.add_argument("--serve", nargs="?", const=8000, type=int, metavar="PORT")
    args = parser.parse_args(argv)
    if args.check:
        build_app()  # prove the app assembles
        print("routes: " + ", ".join(["/", "/health"] + ["/" + r for r in ROUTES]))
        return 0
    if args.serve is not None:
        serve(args.serve)
        return 0
    parser.print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
"""


def _emit_files(model: ProjectModel, package: str, name: str) -> dict[str, str]:
    """Build the {relpath: content} map for the generated web API. Pure + deterministic."""
    routes = _routes(model)
    header = (
        f'"""{model.identity} -- a web API generated by CodeForge from a project model."""\n\n'
        "import json\n\n"
        f"SERVICE = {json.dumps(model.identity)}\n"
        f"ROUTES = {json.dumps(routes)}\n"
        '__version__ = "0.1.0"\n'
    )
    app_py = header + _APP_BODY

    main_py = (
        f'"""{model.identity} -- run the generated web API."""\n\n'
        "import argparse\n\n"
        f"from {package}.app import ROUTES, SERVICE, __version__, build_app, serve\n\n"
        f"PROG = {json.dumps(name)}\n" + _MAIN_BODY
    )

    test_py = f"""from {package}.app import ROUTES, build_app


def _call(path):
    captured = {{}}

    def start_response(status, headers):
        captured["status"] = status

    body = b"".join(build_app()({{"PATH_INFO": path, "REQUEST_METHOD": "GET"}}, start_response))
    import json

    return captured["status"], json.loads(body)


def test_root_lists_the_service():
    status, body = _call("/")
    assert status.startswith("200") and "service" in body


def test_health_is_ok():
    status, body = _call("/health")
    assert status.startswith("200") and body["status"] == "ok"


def test_a_route_responds():
    status, body = _call("/" + ROUTES[0])
    assert status.startswith("200") and body["ok"] is True


def test_an_unknown_path_is_404():
    status, body = _call("/nope")
    assert status.startswith("404") and body["error"] == "not found"
"""

    conftest_py = (
        "import os\nimport sys\n\nsys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))\n"
    )

    desc = json.dumps(model.identity)
    pyproject = (
        "[project]\n"
        f'name = "{name}"\n'
        'version = "0.1.0"\n'
        f"description = {desc}\n\n"
        "[project.scripts]\n"
        f'{name} = "{package}.__main__:main"\n'
    )

    readme = (
        f"# {model.identity}\n\n"
        "A small web API generated by CodeForge from a project model (stdlib only).\n\n"
        f"- source: {model.provenance.source_id} (owner: {model.provenance.owner})\n"
        f"- routes: {', '.join('/' + r for r in routes)}\n\n"
        f"Check: `python -m {package} --check`  ·  Serve: `python -m {package} --serve 8000`\n"
    )

    return {
        f"{package}/__init__.py": '__version__ = "0.1.0"\n',
        f"{package}/app.py": app_py,
        f"{package}/__main__.py": main_py,
        "tests/test_api.py": test_py,
        "conftest.py": conftest_py,
        "pyproject.toml": pyproject,
        "README.md": readme,
    }


def generate_web_api(model: ProjectModel, dest: Path) -> GeneratedArtifact:
    """Generate a runnable web API from a model into an empty `dest`. Reproducible + checksummed."""
    if not model.identity or not model.identity.strip():
        raise GeneratorError("a project model needs a non-empty identity to generate a web API")
    dest = Path(dest)
    if dest.exists() and any(dest.iterdir()):
        raise GeneratorError(f"destination {dest} is not empty; refusing to overwrite")
    package = _package_name(model.identity)
    name = package.replace("_", "-")
    contents = _emit_files(model, package, name)

    checksums: dict[str, str] = {}
    for rel, text in contents.items():
        path = dest / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")
        checksums[rel] = _sha256(text)

    manifest_hash = _sha256("\n".join(f"{r}:{checksums[r]}" for r in sorted(checksums)))
    return GeneratedArtifact(
        name=name,
        package=package,
        dest=str(dest),
        files=sorted(contents),
        checksums=checksums,
        manifest_hash=manifest_hash,
        provenance=model.provenance,
        model_identity=model.identity,
        commands=_routes(model),  # the API's routes (the target's operations)
    )


def validate_runs(artifact: GeneratedArtifact, *, seed_id: str = "_generate") -> ToolRunResult:
    """Prove the generated API RUNS: `python -m <package> --check` builds the app + lists routes,
    exit 0, WITHOUT binding a port (no network in a gate)."""
    return run_tool(
        _target_source(artifact),
        "check",
        seed_id=seed_id,
        kind="build",
        allowlist={"check": [sys.executable, "-m", artifact.package, "--check"]},
    )


def validate_tests(artifact: GeneratedArtifact, *, seed_id: str = "_generate") -> ToolRunResult:
    """Prove the generated API's TESTS PASS: run its pytest suite through the Stage-5 runner."""
    return run_tool(
        _target_source(artifact),
        "pytest",
        seed_id=seed_id,
        kind="test",
        allowlist={
            "pytest": [sys.executable, "-m", "pytest", "tests/", "-q", "-p", "no:cacheprovider"]
        },
    )


def rollback(artifact: GeneratedArtifact) -> None:
    """Remove a generated tree (cleanup/rollback). Idempotent."""
    shutil.rmtree(artifact.dest, ignore_errors=True)


def render_artifact(artifact: GeneratedArtifact) -> str:
    """A human summary of a generated web-API artifact (routes, integrity, provenance)."""
    return "\n".join(
        [
            f"GENERATED TARGET: {artifact.name}  (a web API from '{artifact.model_identity}')",
            f"  package:      {artifact.package}",
            f"  routes:       {', '.join('/' + r for r in artifact.commands)}",
            f"  files ({len(artifact.files)}): {', '.join(artifact.files)}",
            f"  manifest sha: {artifact.manifest_hash[:16]}...",
            f"  provenance:   {artifact.provenance.source_id} "  # noqa: ISC004
            f"(owner: {artifact.provenance.owner}, {artifact.provenance.visibility})",
            f"  path:         {artifact.dest}",
        ]
    )
