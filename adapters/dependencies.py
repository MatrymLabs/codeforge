"""CARD: dependencies -- the dependency gate: every dependency earns its place.

The Dependency Approval Rule (docs/tooling_strategy.md) made machine-checkable. It reads the
declared dependencies from pyproject.toml and the justifications from dependency_ledger.toml,
then reports every dependency that is declared but unjustified (a FAIL) or justified but no
longer declared (a stale WARN). Frameless discipline: stdlib only (tomllib), no new dep to
police the deps. It mutates nothing; it reports a verdict. `make deps` runs it; the test twin
rides `make check`, so an unjustified dependency cannot merge silently.

It also carries an offline ADMISSION SCREEN (`screen <name>`): before a package is ever trusted,
check the NAME for the AI-hallucination / typo-squat risk the supply-chain literature warns is
systemic (an assistant confidently invents `reqeusts` or `python-dateutils`). A name that is not a
valid package name, or is one edit from a well-known package while being neither that package nor
already justified, is flagged. Offline and stdlib-only (no PyPI call, so it never touches the
network in a test); it screens the name, human judgement admits the dependency.

The screen has a second, BEHAVIORAL half (`screen-source <path>`): the name check catches a
hallucinated/typo-squat name, but a real package can carry a malicious install hook - setup.py runs
with the installer's privileges. `install_hook_concerns` statically screens install-time code (by
AST, offline, never executed) for the attack primitives: phoning home, spawning a shell, dynamic
eval/exec, and the decode-then-execute obfuscation shape. Propose-only: it flags for human review.
"""

from __future__ import annotations

import ast
import re
import tomllib
from dataclasses import dataclass
from pathlib import Path

_ROOT = Path(__file__).resolve().parent.parent
_PYPROJECT = _ROOT / "pyproject.toml"
_LEDGER = _ROOT / "dependency_ledger.toml"
_REQUIRED_FIELDS = ("why", "stdlib_alternative", "removable")

# A PEP 503-normalized package name: lowercase alphanumerics plus internal . _ - separators.
_PEP503 = re.compile(r"^[a-z0-9]([a-z0-9._-]*[a-z0-9])?$")

# Well-known PyPI packages an assistant is likely to invent a plausible-but-wrong near-miss of
# (the frequent typo-squat / hallucination targets). Curated, not exhaustive: the point is to catch
# the common one-edit near-misses, not to mirror the whole index. A declared name one edit from one
# of these, but neither that package nor already justified in our ledger, is suspect until verified.
POPULAR_PACKAGES = frozenset(
    {
        "requests",
        "urllib3",
        "httpx",
        "aiohttp",
        "numpy",
        "pandas",
        "scipy",
        "matplotlib",
        "scikit-learn",
        "torch",
        "tensorflow",
        "flask",
        "django",
        "fastapi",
        "starlette",
        "pydantic",
        "sqlalchemy",
        "uvicorn",
        "gunicorn",
        "websockets",
        "pytest",
        "hypothesis",
        "pyyaml",
        "click",
        "rich",
        "boto3",
        "pillow",
        "beautifulsoup4",
        "python-dateutil",
        "setuptools",
        "wheel",
        "cryptography",
        "certifi",
        "jinja2",
        "typing-extensions",
        "packaging",
        "ruff",
        "mypy",
        "bandit",
        "pip-audit",
    }
)


def _edit_distance(a: str, b: str, *, cap: int = 2) -> int:
    """Levenshtein distance between two names, capped (we only care whether it is exactly 1).
    Stdlib only, no dependency. Returns `cap + 1` once the distance provably exceeds the cap."""
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]


def admission_concerns(
    name: str,
    *,
    trusted: frozenset[str],
    popular: frozenset[str] = POPULAR_PACKAGES,
) -> list[str]:
    """Screen one package NAME for admission (offline). Returns the concerns, empty when it is
    clean. Catches an invalid name, or a name one edit from a popular package while being neither
    that package nor already `trusted` (justified in our ledger): the typo-squat / hallucination
    signal. Existence on PyPI is deliberately NOT checked here (that needs the network); this is the
    offline first line, and human judgement admits the dependency after verifying it."""
    canon = _canonical(name)
    if not _PEP503.match(canon):
        return [f"{canon!r} is not a valid package name (PEP 503)"]
    if canon in trusted or canon in popular:
        return []  # already justified in our ledger, or itself the well-known package
    for pop in sorted(popular):
        if _edit_distance(canon, pop) == 1:
            return [
                f"{canon!r} is one edit from the popular package {pop!r}: possible typo-squat or "
                f"a hallucinated name. Verify it is the package you mean before trusting it."
            ]
    return []


def screen_name(name: str, ledger: Path = _LEDGER) -> list[str]:
    """Screen a proposed dependency name against the trusted (justified) set + the popular set."""
    trusted = frozenset(read_ledger(ledger))
    return admission_concerns(name, trusted=trusted)


# --- behavioral admission screen: what does the package DO when it is installed? -----------------
# The name screen catches a hallucinated/typo-squat NAME; this catches malicious BEHAVIOR in the
# install-time code. setup.py runs with the installer's privileges, so a package that phones home,
# spawns a shell, or decodes-and-executes a payload during install is the supply-chain attack shape.
# Screened by static AST, OFFLINE, and NEVER executed - reading the code is the whole point.
_NETWORK_MODULES = frozenset(
    {"socket", "urllib", "http", "ftplib", "telnetlib", "smtplib", "requests", "httpx", "aiohttp"}
)
_PROCESS_MODULES = frozenset({"subprocess", "pty"})
_DECODE_MODULES = frozenset({"base64", "marshal", "zlib", "binascii", "codecs"})
_EXEC_BUILTINS = frozenset({"eval", "exec", "compile", "__import__"})
_PROCESS_CALLS = frozenset(
    {"os.system", "os.popen", "os.execv", "os.execve", "os.execvp", "os.spawnv", "os.spawnl"}
)


def _dotted(node: ast.expr) -> str:
    """Best-effort dotted name for a call target: `os.system`, `subprocess.run`, or bare `exec`."""
    parts: list[str] = []
    while isinstance(node, ast.Attribute):
        parts.append(node.attr)
        node = node.value
    if isinstance(node, ast.Name):
        parts.append(node.id)
    return ".".join(reversed(parts))


def install_hook_concerns(source: str) -> list[str]:
    """Statically screen install-time Python (a setup.py's source) for supply-chain-attack behavior.

    Offline and stdlib-only: parses `source` with `ast` and NEVER executes it. Flags install-time
    network access, shell/process execution, dynamic code execution (eval/exec/compile), and the
    decode-then-execute obfuscation pattern - the primitives a malicious package uses to run a
    payload the moment it is installed. Returns the concerns (empty == clean); an unparseable script
    is itself a concern (it cannot be screened safely). Propose-only: the verdict informs a human,
    it admits nothing.
    """
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        return [
            f"install script does not parse as Python ({exc.msg}); cannot be screened safely - "
            f"treat as suspicious"
        ]
    imported: set[str] = set()
    calls: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            imported.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            imported.add(node.module.split(".")[0])
        elif isinstance(node, ast.Call):
            calls.add(_dotted(node.func))
    concerns: list[str] = []
    if net := sorted(imported & _NETWORK_MODULES):
        concerns.append(
            f"install-time network access (imports {', '.join(net)}): a package should not phone "
            f"home when it is installed"
        )
    proc = sorted(imported & _PROCESS_MODULES) + sorted(c for c in calls if c in _PROCESS_CALLS)
    if proc:
        concerns.append(
            f"install-time process/shell execution ({', '.join(proc)}): the setup script spawns "
            f"commands - confirm it is benign (e.g. a git version) and not a dropper"
        )
    if execs := sorted(c for c in calls if c.rsplit(".", 1)[-1] in _EXEC_BUILTINS):
        concerns.append(
            f"dynamic code execution at install time ({', '.join(execs)}): eval/exec/compile runs "
            f"code that static review cannot see"
        )
        if decode := sorted(imported & _DECODE_MODULES):
            concerns.append(
                f"obfuscated payload: decode ({', '.join(decode)}) feeding dynamic execution - the "
                f"classic hidden install-hook shape"
            )
    return concerns


def screen_source(path: Path) -> list[str]:
    """Screen a package's install-time code at `path` (a setup.py file, or a directory containing
    one). Offline: reads the source and screens it via `install_hook_concerns`, never running it.
    A missing file raises loud (a screen you cannot perform must not read as 'clean')."""
    path = Path(path)
    if path.is_dir():
        path = path / "setup.py"
    return install_hook_concerns(path.read_text(encoding="utf-8", errors="replace"))


class LedgerError(RuntimeError):
    """A malformed ledger or pyproject fails loud, never silently passes."""


def _canonical(name: str) -> str:
    """PEP 503 normalize + strip extras/version markers: 'bandit[toml]>=1' -> 'bandit'."""
    head = re.split(r"[<>=!~;\[ ]", name.strip(), maxsplit=1)[0]
    return re.sub(r"[-_.]+", "-", head).lower()


@dataclass(frozen=True)
class Declared:
    """The dependencies pyproject.toml actually asks for, canonicalized."""

    runtime: frozenset[str]
    dev: frozenset[str]

    @property
    def all(self) -> frozenset[str]:
        return self.runtime | self.dev


def read_declared(path: Path = _PYPROJECT) -> Declared:
    """Parse the runtime + dev dependency names from pyproject.toml (fails loud if absent)."""
    if not path.is_file():
        raise LedgerError(f"pyproject not found: {path}")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    project = data.get("project", {})
    optional = project.get("optional-dependencies", {})
    runtime = {_canonical(x) for x in project.get("dependencies", [])}
    # Optional FEATURE extras (e.g. `ai`) are runtime capabilities, not dev tooling: they
    # still earn their place, so fold every non-dev extra into the runtime set the gate audits.
    for group, items in optional.items():
        if group == "dev":
            continue
        runtime |= {_canonical(x) for x in items}
    dev = {_canonical(x) for x in optional.get("dev", [])}
    return Declared(frozenset(runtime), frozenset(dev))


def read_ledger(path: Path = _LEDGER) -> dict[str, dict[str, str]]:
    """Parse the justification rows; a missing file or an incomplete row fails loud."""
    if not path.is_file():
        raise LedgerError(f"dependency ledger not found: {path}")
    data = tomllib.loads(path.read_text(encoding="utf-8"))
    entries: dict[str, dict[str, str]] = {}
    for scope in ("runtime", "dev"):
        for name, row in data.get(scope, {}).items():
            if not isinstance(row, dict):
                raise LedgerError(f"[{scope}.{name}] must be a table of justification fields")
            missing = [f for f in _REQUIRED_FIELDS if not str(row.get(f, "")).strip()]
            if missing:
                raise LedgerError(
                    f"[{scope}.{name}] missing required field(s): {', '.join(missing)}"
                )
            entries[_canonical(name)] = {
                "scope": scope,
                **{f: str(row[f]) for f in _REQUIRED_FIELDS},
            }
    return entries


@dataclass(frozen=True)
class DependencyAudit:
    """The verdict: what is justified, what is unjustified (FAIL), what is stale (WARN)."""

    ok: tuple[str, ...]
    unjustified: tuple[str, ...]
    stale: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return not self.unjustified


def audit_dependencies(pyproject: Path = _PYPROJECT, ledger: Path = _LEDGER) -> DependencyAudit:
    """Compare declared deps against the ledger; unjustified declarations fail the gate."""
    declared = read_declared(pyproject)
    filed = set(read_ledger(ledger))
    return DependencyAudit(
        ok=tuple(sorted(declared.all & filed)),
        unjustified=tuple(sorted(declared.all - filed)),
        stale=tuple(sorted(filed - declared.all)),
    )


def format_audit(audit: DependencyAudit) -> str:
    """Render the verdict for a human (the `make deps` readout / `terminal deps`)."""
    verdict = "PASS" if audit.passed else "FAIL"
    lines = [
        "DEPENDENCY GATE - every dependency earns its place (frameless Python)",
        f"  {len(audit.ok)} justified, {len(audit.unjustified)} unjustified, "
        f"{len(audit.stale)} stale  ->  {verdict}",
        "",
    ]
    if audit.unjustified:
        lines.append("  UNJUSTIFIED (declared in pyproject, no ledger row):")
        lines += [
            f"    - {name}  (add a row to dependency_ledger.toml)" for name in audit.unjustified
        ]
        lines.append("")
    if audit.stale:
        lines.append("  STALE (ledger row, no longer declared):")
        lines += [
            f"    - {name}  (remove its row from dependency_ledger.toml)" for name in audit.stale
        ]
        lines.append("")
    if audit.passed and not audit.stale:
        lines.append("  Every declared dependency has a justification. The ledger is clean.")
    return "\n".join(lines).rstrip() + "\n"


def render_dependencies(pyproject: Path = _PYPROJECT, ledger: Path = _LEDGER) -> str:
    """The gate's human report (used by `make deps` and the in-game terminal)."""
    return format_audit(audit_dependencies(pyproject, ledger))


def main(argv: list[str] | None = None) -> int:
    """`make deps`: print the gate verdict; exit non-zero if any dependency is unjustified.
    `python -m adapters.dependencies screen <name>`: run the name admission screen.
    `... screen-source <path>`: run the behavioral install-hook screen on a setup.py."""
    import sys

    args = list(sys.argv[1:] if argv is None else argv)
    if len(args) >= 2 and args[0] == "screen-source":
        try:
            concerns = screen_source(Path(args[1]))
        except OSError as exc:
            print(f"behavioral screen: {exc}")
            return 2
        if not concerns:
            print(
                f"behavioral screen: {args[1]} shows no install-time danger "
                f"(no network / shell / eval / decode-exec)."
            )
            return 0
        print(f"behavioral screen: {args[1]} has concerns (human review before trusting):")
        for concern in concerns:
            print(f"  - {concern}")
        return 1
    if len(args) >= 2 and args[0] == "screen":
        try:
            concerns = screen_name(args[1])
        except LedgerError as exc:
            print(f"admission screen: {exc}")
            return 2
        canon = _canonical(args[1])
        if not concerns:
            print(
                f"admission screen: {canon!r} looks admissible (valid name, no typo-squat signal)."
            )
            return 0
        print(f"admission screen: {canon!r} has concerns:")
        for concern in concerns:
            print(f"  - {concern}")
        return 1
    try:
        audit = audit_dependencies()
    except LedgerError as exc:
        print(f"dependency gate: {exc}")
        return 2
    print(format_audit(audit))
    return 0 if audit.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
