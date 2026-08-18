# Windows PC Baseline Reference — Matrym Labs Polyglot Dev Migration (Pi 5 → Windows 11 / RTX 4090)

## TL;DR

- **Go native Windows, not WSL2, for your primary loop.** Every tool in your stack (uv, ruff, mypy, pytest, cargo/rustup, Go, golangci-lint, JDK/Gradle, Godot, node/npm, gh, gitleaks, Trivy/Syft/Grype) is first-class on native Windows in 2025-2026, and Rider is a native Windows app. WSL2’s `/mnt/c` bridge runs file operations at a fraction of native speed (Webbert Takken’s benchmark measured `/mnt/c` access averaging ~6% of native, random reads as low as 3%, and `git status`/installs 10-20x slower across the 9P boundary) — so a WSL2-native/Windows-repo hybrid is the worst of both worlds. Keep `C:\Projects\MatrymLabs` native; the Raspberry Pi already gives you a real Linux/ARM target.
- **Three configuration fixes deliver most of the day-one gains:** Defender exclusions on your project root + package caches + build dirs (real build-speed impact), `core.longpaths=true` + registry `LongPathsEnabled=1` (Rust `target/`, `node_modules`, and worktrees overflow the 260-char limit), and a committed `.gitattributes` with `* text=auto eol=lf` + `git add --renormalize .` to keep line endings sane across Windows and the Pi.
- **Migrate orchestration from GNU Make to Task (Taskfile.yml), fix the JDK 21/24 mismatch with Gradle toolchains + the foojay plugin, and treat the 4090 as an optional local-LLM side rig — not a replacement for Claude Code/Codex.** Access the box over Tailscale rather than open ports.

## Key Findings

### 1. The native-vs-WSL2 ruling (the central decision)

**Ruling: run your entire primary toolchain natively on Windows. Do not put repos on `/mnt/c` under WSL2.** Reasoning:

- **Filesystem physics.** WSL2 is a lightweight VM; it reaches Windows files (`/mnt/c`) over the 9P network protocol. Webbert Takken’s WSL filesystem benchmark found that “WSL accessing the Windows filesystem (`/mnt/c/`) averages at ~6% of native performance, with random reads as low as 3%… Windows accessing the WSL filesystem (`\\wsl.localhost\`) averages at ~14%, with sequential writes for large files dropping below 1% performance.” In practice `yarn install`, dev servers, and `git status` take 10-20x longer across that boundary. Multiple 2026 guides (How-To Geek, Ceos3c, Lorbic for Go) independently conclude: keep code on the *same* OS filesystem as the tools that touch it.
- **The trap for your setup.** The “correct” WSL2 pattern is repos on the *Linux* ext4 filesystem, edited by Linux tools. But your IDE (Rider) is a native Windows app, your AI agents run in Windows terminals, and you view over NoMachine to the Windows desktop. Bridging Rider on Windows to repos inside WSL2 re-introduces the cross-boundary tax and adds interpreter-path confusion. So the only two coherent options are “all native Windows” or “all inside WSL2 (Linux Rider, Linux agents).” Given RTX 4090 + Godot + Rider + NoMachine all being Windows-native, **all-native Windows wins.**
- **You already have Linux.** The Pi 5 (aarch64 Debian) is your ARM smoke-test and Linux parity check. GitHub Actions `ubuntu-latest` is your Linux CI. You do not need WSL2 for Linux parity. Keep WSL2 installed only as an optional convenience for the rare bash-only tool (e.g. running `shellcheck` or a bash hook), never for your repos.

**Tool-by-tool native Windows status (2025-2026, all verified first-class):**

- **uv** — native Windows binary, `winget install astral-sh.uv`. Per Astral’s launch post, uv is “8-10x faster than pip and pip-tools without caching, and 80-115x faster when running with a warm cache.” First-class.
- **ruff, mypy, pytest** — pure-Python / Rust-based, install via uv; fully native. pytest-xdist `-n auto` works on Windows.
- **cargo/rustup** — `winget install Rustlang.Rustup`; native, use the MSVC toolchain (default).
- **Go** — `winget install GoLang.Go`; native, first-class.
- **golangci-lint** — native Windows binary.
- **JDK/Gradle** — Temurin via winget; Gradle native. (JDK mismatch fix below.)
- **Godot 4 + gdtoolkit/gdunit4** — Godot is native Windows; gdtoolkit is pip-installable (via uv); gdunit4 runs in-engine.
- **node/npm** — native; manage with fnm (`winget install Schniz.fnm`). Claude Code’s npm install works natively on Windows.
- **gh CLI** — `winget install GitHub.cli`; native.
- **gitleaks, Trivy, Syft, Grype** — all ship native Windows binaries (Go-based). First-class.
- **pre-commit** — installs fine, BUT hooks written in bash break on native Windows (see §6c).
- **GNU make** — available via scoop/choco/mingw but a second-class citizen on Windows; recommend migrating to Task (see §6a).

### 2. Windows configuration that materially affects performance

**(a) Windows Defender exclusions.** Real-time scanning of large, rapidly-changing file trees (dependency dirs, build outputs, language-server caches) is a well-documented cause of slow builds, crawling package installs, and fans spinning on Windows dev machines. JetBrains documents that Rider/IntelliJ themselves offer to add Defender exclusions because AV materially impacts build speed. **Exclude:** your project root, package caches, and build output dirs. Exact PowerShell (run elevated):

```powershell
# Folders
Add-MpPreference -ExclusionPath "C:\Projects\MatrymLabs"
Add-MpPreference -ExclusionPath "$env:USERPROFILE\.cargo"
Add-MpPreference -ExclusionPath "$env:USERPROFILE\.rustup"
Add-MpPreference -ExclusionPath "$env:USERPROFILE\.gradle"
Add-MpPreference -ExclusionPath "$env:USERPROFILE\go"
Add-MpPreference -ExclusionPath "$env:LOCALAPPDATA\uv"
Add-MpPreference -ExclusionPath "$env:LOCALAPPDATA\npm-cache"
Add-MpPreference -ExclusionPath "$env:USERPROFILE\AppData\Local\JetBrains"
# Processes (files opened by these are skipped in real-time)
Add-MpPreference -ExclusionProcess "cargo.exe"
Add-MpPreference -ExclusionProcess "rustc.exe"
Add-MpPreference -ExclusionProcess "go.exe"
Add-MpPreference -ExclusionProcess "node.exe"
Add-MpPreference -ExclusionProcess "python.exe"
Add-MpPreference -ExclusionProcess "java.exe"
Add-MpPreference -ExclusionProcess "git.exe"
```

**Security tradeoff, stated honestly:** Microsoft Learn’s own guidance (“Exclusions in Microsoft Defender Antivirus”) states: “Every exclusion is a protection gap that lowers your defenses, so use exclusions sparingly. Define an exclusion only to resolve a specific problem, such as a performance or app compatibility issue, and consider alternatives like custom indicators first.” An excluded folder is not scanned in real time — if malware lands in `C:\Projects\MatrymLabs` (e.g. via a poisoned npm/pip/cargo dependency), Defender won’t catch it there. Mitigate by (1) keeping real-time protection ON everywhere else, (2) scoping exclusions to specific dev paths rather than whole drives, and (3) leaning on supply-chain scanning (gitleaks, Trivy, `cargo audit`, `pip-audit`) in your checks pipeline.

**(b) NTFS long paths.** Windows’ legacy MAX_PATH is 260 chars; Rust `target/`, `node_modules`, and *especially git worktrees* (which append a longer base path) overflow it — misreported by git as bizarre errors including “Out of diskspace.”  Enable both layers:

```powershell
# Registry (system-wide, needs admin + reboot/logoff)
Set-ItemProperty -Path "HKLM:\SYSTEM\CurrentControlSet\Control\FileSystem" -Name "LongPathsEnabled" -Value 1
```

```bash
git config --system core.longpaths true   # or --global if no admin
```

Even with both enabled, keep the root short (`C:\Projects\MatrymLabs` is good; avoid deep user-profile paths).

**(c) Line endings (Windows + Linux Pi mirror).** The canonical fix is a committed `.gitattributes`, not per-machine `core.autocrlf`. Recommended root `.gitattributes` for your polyglot repos:

```
* text=auto eol=lf
*.sh    text eol=lf
*.py    text eol=lf
*.rs    text eol=lf
*.go    text eol=lf
*.kt    text eol=lf
*.gd    text eol=lf
*.ps1   text eol=crlf
*.bat   text eol=crlf
*.cmd   text eol=crlf
# Binaries
*.png binary
*.jpg binary
*.nes binary
*.ico binary
```

After adding it: `git add --renormalize . && git commit -m "Normalize line endings"`. Set `core.autocrlf=false` on Windows and let `.gitattributes` be the single source of truth (this keeps shell scripts and Python LF-clean for the Pi and CI, while PowerShell/batch stay CRLF). Known pitfall: CI/containers default to `autocrlf=false`, so relying on local autocrlf breaks in CI — `.gitattributes` with explicit `eol=lf` avoids that. 

**(d) Case sensitivity.** NTFS is case-insensitive (case-preserving); ext4 on the Pi is case-sensitive. Files that differ only in case (e.g. `Readme.md` vs `README.md`) coexist on the Pi but collide on Windows. Add the pre-commit hook `check-case-conflict` (from pre-commit-hooks) to catch this before it hits the Pi.  Windows supports per-directory case sensitivity via `fsutil file setCaseSensitiveInfo <dir> enable`, but do not rely on it for your repos — treat case-collisions as bugs and prevent them.

**(e) Developer Mode + symlinks.** Your repos had committed `.venv` symlinks — a problem on Windows. POSIX symlinks require either admin rights or **Developer Mode** enabled (Settings → System → For developers → Developer Mode), plus `git config --global core.symlinks true` (and Git for Windows installed with symlink support). Without these, git checks out a symlink as a plain text file containing the link target path. **Recommendation:** enable Developer Mode, set `core.symlinks true`, but *stop committing `.venv` symlinks entirely* — `.venv` should be gitignored and recreated per-machine via `uv venv` / `uv sync`. Committed virtualenv symlinks are non-portable across OS and architecture (your Pi is aarch64, the PC is x86-64) and will break regardless.

**(f) PowerShell vs Git Bash vs cmd.** For agent-driven terminal work and running your check scripts, **PowerShell 7 (pwsh)** is the sensible Windows default; Git Bash (MSYS2) is useful for the occasional bash script but has path-translation quirks. Set execution policy so scripts run without friction: `Set-ExecutionPolicy -Scope CurrentUser RemoteSigned`. If you migrate orchestration to Task (§6a), the shell question mostly disappears — Task runs commands cross-platform.

**(g) Windows Terminal.** Use Windows Terminal (ships with Win 11) as the host for both AI agents and your shells; it supports tabs/panes and profiles for pwsh, Git Bash, and WSL if needed. Give each AI agent its own tab/profile.

**(h) Power settings + NoMachine.** For long builds and reliable remote access, prevent sleep:

```powershell
powercfg /change standby-timeout-ac 0
powercfg /change hibernate-timeout-ac 0
powercfg /change monitor-timeout-ac 15
```

Set the power plan to High Performance (or Ultimate Performance). NoMachine specifically: a machine that sleeps or turns off its display can drop remote sessions, so disable standby on AC. See §5e for NoMachine tuning.

### 3. Toolkit availability and version management

**(a) winget vs scoop vs chocolatey.** For a solo dev machine in 2025-2026, **winget is the right primary** (built into Windows 11, no setup, SHA256-verified manifests, and — crucially — declarative reproducibility via WinGet Configuration). Add **scoop** as a secondary for CLI dev tools that want no-admin, per-user, multi-version installs. Skip Chocolatey unless you hit a package only it carries (its best features are increasingly paywalled and it’s oriented to enterprise fleet management you don’t need).

**Reproducible bootstrap — use WinGet Configuration (DSC).** Microsoft’s recommended reproducible approach is a declarative `.winget/configuration.dsc.yaml` file applied with `winget configure` (requires WinGet v1.6.2631+, shipped in the current App Installer on Win 11). It’s idempotent, supports assertions (OS version, Developer Mode) and `dependsOn`, and uses PowerShell DSC resources  (`Microsoft.WinGet.DSC/WinGetPackage`). Commands: `winget configure validate <file>`, `winget configure show -f <file>`, `winget configure --file <file>`. Sample resource:

```yaml
# yaml-language-server: $schema=https://aka.ms/configuration-dsc-schema/0.2
properties:
  configurationVersion: 0.2.0
  resources:
    - resource: Microsoft.WinGet.DSC/WinGetPackage
      id: git
      directives: { description: Install Git }
      settings: { id: Git.Git, source: winget }
```

Microsoft’s own security warning: never run a configuration file without reviewing the referenced DSC resources. For a quick package-list snapshot use `winget export -o apps.json --include-versions --accept-source-agreements` and restore with `winget import -i apps.json --accept-package-agreements --accept-source-agreements`. Caveat: export only captures apps in the winget repo and can’t detect some versions (e.g. rustup shows “Unknown”), so it’s a package list, not a full environment.

**Verified winget IDs for your stack:**

```
EclipseAdoptium.Temurin.21.JDK
EclipseAdoptium.Temurin.24.JDK
Git.Git
GoLang.Go
Rustlang.Rustup
astral-sh.uv
Schniz.fnm
GitHub.cli
Task.Task
Casey.Just
Tailscale.Tailscale
Ollama.Ollama
```

**(b) Per-language version managers.**

- **Python:** uv manages Python versions natively (`uv python install 3.13`, `uv python pin 3.13`). No pyenv needed.
- **Rust:** rustup (`rustup toolchain install`, `rustup override`). Note winget can’t track rustup’s version — update via `rustup self update && rustup update`, not `winget upgrade`.
- **Go:** the Go toolchain’s built-in `toolchain` directive in `go.mod` (Go 1.21+) auto-downloads the specified Go version; for multiple explicit versions use `go install golang.org/dl/go1.XX@latest`.
- **JDK — the answer to your JDK 21 vs 24 mismatch (SDKMAN doesn’t work on native Windows):** Two-layer fix. (1) For *builds*, the canonical fix is **Gradle Java Toolchains + the `foojay-resolver-convention` plugin** — the build declares the JDK it needs and Gradle auto-provisions/downloads it regardless of the machine’s default JDK, so local and CI match automatically. In `settings.gradle.kts`: `plugins { id("org.gradle.toolchains.foojay-resolver-convention") version "1.0.0" }`;  in `build.gradle.kts`: `java { toolchain { languageVersion = JavaLanguageVersion.of(21) } }`. Gradle 8.13+ also lets you pin the daemon JVM (`./gradlew updateDaemonJvm --jvm-version=21 --jvm-vendor=adoptium`, writing `gradle/gradle-daemon-jvm.properties`; IntelliJ/Rider support from 2025.1+). (2) For *general CLI/IDE JDK switching* on native Windows, **mise** now runs natively on Windows PowerShell/cmd (no WSL) and manages Temurin per-project (`mise use java@temurin-21`), writing a `mise.toml` and setting `JAVA_HOME` automatically — it’s the modern SDKMAN replacement for Windows. `jenv` does NOT work on native Windows; `jabba` works but doesn’t persist `JAVA_HOME`. Install both Temurins via winget as the base.
- **RetroForge specifically:** point its Gradle toolchain at JDK 21 (`languageVersion = JavaLanguageVersion.of(21)`) with the foojay plugin; then even if CI runs Java 24 or your default JDK is 24, Gradle compiles/tests against 21 consistently. This eliminates the “JDK 21 local vs Java 24 CI” divergence at its root.

**(c) Node version management.** For Claude Code (npm) on Windows, use **fnm** (`winget install Schniz.fnm`) — Rust-based, fast, native Windows, reads `.nvmrc`/`.node-version`, and is the 2026 consensus pick over nvm-windows (which is slower and less maintained). Volta is the alternative if you want per-repo pinning written into `package.json`; for a solo founder, fnm is simpler. Add to `$PROFILE`: `fnm env --use-on-cd | Out-String | Invoke-Expression`. 

**(d) Reproducibility.** Keep a single `.winget/configuration.dsc.yaml` in a `machine-bootstrap` repo (one of your 13), version-pinned; supplement with `uv.lock`, `Cargo.lock`, `go.sum`, Gradle version catalogs, and `.nvmrc`/`mise.toml`. That combination reconstructs the whole machine.

### 4. Multi-repo + worktree practices on Windows

**(a) Worktrees.** Git worktrees work on Windows but have three known failure modes: (1) **path length** — worktree paths append to a base path and overflow MAX_PATH;  multiple 2025 bug reports show worktree add/removal failing with “Filename too long” even at ~74-char roots. Enable long paths (§2b) AND keep worktree roots short. (2) **locks from Defender/indexing/IDE file watchers** — a background scanner or Rider’s file watcher holding a handle causes worktree remove failures; the Defender exclusion (§2a) and Search-index exclusion (§4b) reduce this. (3) Use `git worktree remove --force` (twice if locked) when a worktree won’t delete.  Recommended layout: keep worktrees in a short sibling dir, e.g. main checkouts at `C:\Projects\MatrymLabs\<repo>` and worktrees at `C:\Projects\wt\<repo>-<branch>`, not deeply nested under the main checkout.

**(b) Windows Search indexing.** Exclude `C:\Projects\MatrymLabs` from Windows Search indexing (Settings → Privacy & security → Searching Windows → Add excluded folder). Indexing thousands of churning source/build files wastes I/O and can hold file handles that conflict with git/worktrees. Dev folders gain nothing from being indexed.

**(c) Repo layout — avoid cloud-synced paths.** Keep everything under `C:\Projects\MatrymLabs` (short, non-synced). **Never** put git repos inside OneDrive/Dropbox-synced folders — a well-documented cause of `.git` corruption (“Could not initialize libgit… not a git repository”),  because the sync client races git’s atomic file operations.  Git-LFS/DVC on synced folders is equally risky. OneDrive on Win 11 even shows a warning: “Concurrent access to OneDrive synced folders might corrupt repositories.”  Verify `C:\Projects` is outside OneDrive’s scope (Windows 11 sometimes redirects Desktop/Documents into OneDrive by default).

**(d) The Pi as git mirror.** Robust pattern: use **GitHub (or your chosen hub) as the origin**, and have the Pi run a scheduled `git fetch --all --prune` (or `git pull --ff-only`) pull-mirror on cron, plus periodic `git fsck`. This is safer than pushing directly PC→Pi. For a true mirror, `git clone --mirror` on the Pi and `git remote update` on cron. Cross-platform gotchas when the same repos live on both Windows (NTFS) and Pi (ext4/aarch64): (1) **line endings** — solved by the committed `.gitattributes` above; (2) **symlinks** — don’t commit them (recreate `.venv` per-machine); (3) **file modes** — set `git config core.fileMode false` on Windows so executable-bit differences don’t create phantom diffs; (4) **case collisions** — the `check-case-conflict` hook. Never build in the same working directory across both machines simultaneously; treat the Pi as fetch/verify/smoke-test only.

### 5. Utilizing the hardware (RTX 4090 + high-core CPU)

**(a) What actually uses the cores.** Your build/test workloads parallelize well; set them explicitly:

- **pytest:** `pytest -n auto` (pytest-xdist). `-n auto` counts *physical* cores; `-n logical` uses logical (hyperthreaded) cores and needs psutil or Python 3.13+. For a high-core CPU, `-n auto` is usually optimal because per-worker overhead grows; benchmark `auto` vs `logical` vs a fixed number. Put `addopts = -n auto` in `pyproject.toml`. Watch out: below ~50 tests, parallelism is a net loss.
- **cargo:** parallel by default; tune with `cargo build --jobs N` or `CARGO_BUILD_JOBS`. On a high-core box the default (all cores) is usually right; if you hit RAM pressure during heavy Rust builds, cap jobs.
- **Go:** `go build`/`go test` use GOMAXPROCS (all cores) by default; `go test -p N` controls package-level parallelism and `-parallel N` in-test parallelism.
- **Gradle:** enable `org.gradle.parallel=true`, `org.gradle.caching=true`, and set `org.gradle.workers.max` in `gradle.properties`; the daemon reuses JVMs across builds.
- **golangci-lint:** concurrency defaults to number of cores; tune `--concurrency N` (or `run.concurrency` in config).

**(b) RAM disk / NVMe scratch.** With a modern NVMe SSD plus Defender exclusions, a RAM disk is generally **not worth it in 2025-2026** for these workloads — the bottleneck was AV scanning and the 260-char/9P issues, not raw disk throughput. Skip the RAM disk; put build outputs on the fast NVMe and exclude them from Defender/indexing. Reconsider only if profiling shows disk I/O as the actual bottleneck.

**(c) What the RTX 4090 is genuinely good for in a dev/agent workflow — honest assessment.**

- **Genuinely useful:** local LLM inference. The 4090’s 24 GB VRAM runs a 32B-class coding model at Q4_K_M fully on-GPU.  Qwen3-Coder 32B at Q4_K_M is the standout — per BestLLMfor’s RTX 4090 benchmark it “scores 71.4% on SWE-Bench Verified and sustains 48–54 tok/s at 32k context… within 4 points of Cursor’s Composer-2 (75.1%) and ahead of GPT-5.1-mini (68.9%).” Newer MoE picks (e.g. a Gemma-class 26B-A4B) hit ~85 tok/s at ~16 GB. Serve via Ollama or LM Studio (llama.cpp server gives the best agentic latency).
- **Godot:** the 4090 accelerates Godot 4 editor/rendering and any 3D game-client work — a real, direct benefit for your planned Godot clients.
- **What it does NOT help:** compilation (cargo/go/gradle/mypy are CPU/IO-bound — the GPU sits idle), pytest, linting, git operations. Do not expect the 4090 to speed up builds or tests at all.

**(d) Local model vs cloud agents — is there a case for a solo founder?** Honest take: your primary agents (Claude Code, Codex) are cloud frontier models and remain the right main drivers — a local 32B model is not competitive with them for hard agentic work. But there is a *narrow, real* supplementary case on the 4090: (1) **cheap bulk / privacy-sensitive tasks** — mass lint-fix, docstring/comment generation, commit-message drafting, and review passes where frontier quality isn’t required and you’d rather not pay per-token; (2) **local embedding/semantic search** over your 13 repos (e.g. nomic-embed-text) for fast codebase retrieval, which fits alongside a 32B model in VRAM. Verdict: **set it up as a background convenience (Ollama + a coding model + an embedder), but don’t let it become a yak-shaving project.** It’s a supplement, not a substitute. If you find yourself tuning quantization instead of shipping, stop.

**(e) NoMachine tuning + alternatives.** For a *coding* workload (text sharpness matters more than frame rate), enable NoMachine’s H.264 hardware encoding (it supports NVENC on the 4090), and if text looks soft, push the “display quality vs speed” slider toward quality and disable network-adaptive downscaling. NoMachine’s NX tech is fine and free for this. Brief alternative comparison: **RDP 10+ (built into Windows Pro) often gives the crispest text** for pure desktop/coding work and is worth trying via Tailscale; **Parsec** excels at low-latency GPU streaming (great if you’re testing Godot game clients remotely) but is gaming-oriented; **Moonlight+Sunshine** (NVENC) is the best free low-latency option if you later want game-client streaming. For day-to-day coding, RDP-over-Tailscale or NoMachine are both fine.

### 6. Checks orchestration cross-platform

**(a) Make vs Task vs just on Windows.** GNU Make is a second-class citizen on Windows (tab-sensitivity, Unix-centric shell assumptions, needs mingw/scoop/choco to exist at all, and your bash-flavored recipes break). For a Windows-primary polyglot repo driven by AI agents, **migrate to Task (Taskfile.yml)**: a single Go binary (`winget install Task.Task`), first-class on Windows, YAML-based (agents parse/edit it easily), built-in `--watch`, cross-platform OS-postfix includes (`Taskfile_{{OS}}.yml`),  and parallel `deps`. **just** is the other strong option (closer to Make syntax, great for argument-passing) but is a command runner without file-dependency tracking. Recommendation: **Task**, because YAML is the friendliest format for Claude Code/Codex to read and modify, and it maps cleanly onto your existing target names. Keep the same targets: `lint`, `typecheck`, `test`, `security`, `mutation`, `build`. Migration note: your Makefile’s per-language commands (uv/ruff/mypy/pytest, clippy/rustfmt, golangci-lint, gdtoolkit/gdunit4) move verbatim into Taskfile `cmds:`; the only real work is translating shell-specific bits and `.PHONY` targets.

**(b) GitHub Actions: ubuntu-latest CI while dev is Windows.** Real “works on my machine” divergence risk (line endings, path separators, case sensitivity, shell). Mitigations: (1) run a **matrix** including `windows-latest` for at least the fast checks (lint/typecheck/test) so Windows-specific breakage is caught; (2) keep the Pi in the loop as your ARM/Linux smoke-test; (3) commit `.gitattributes` (§2c) and set `core.fileMode false` to kill the most common divergences; (4) optionally use **act** to run Actions locally in containers before pushing. For your case, a `[ubuntu-latest, windows-latest]` matrix on the core checks plus the Pi as ARM validation is the pragmatic triangle.

**(c) pre-commit on Windows.** The framework installs and runs on Windows, and Python/Rust/Go-based hooks (ruff, mypy, gitleaks, etc.) work fine. **What breaks: hooks with `#!/bin/bash` shebangs** — native Windows git can’t spawn them (“cannot spawn … No such file or directory”), and `#!/bin/sh` is a non-solution for cross-platform.  Fixes: (1) prefer hooks distributed as the pre-commit framework’s language-native hooks (they bring their own interpreter) rather than local bash scripts; (2) rewrite any local bash hooks as PowerShell or Python; (3) add the Windows-safety hooks `check-case-conflict`, `check-illegal-windows-names`, `check-symlinks` from pre-commit-hooks.  Keep secrets scanning (gitleaks) as a pre-commit hook — it’s a native binary.

**(d) JDK 21/24 as a case study.** As in §3b: the mismatch is solved *at the root* by Gradle toolchains + `foojay-resolver-convention` — declare `languageVersion = JavaLanguageVersion.of(21)` for RetroForge and Gradle provisions JDK 21 locally and in CI identically, regardless of what JDK is default on the box or the runner. Strictly better than manually aligning JAVA_HOME across machines.

### 7. Security baseline for the dev PC

**(a) Remote access — Tailscale, not open ports.** Do not port-forward NoMachine/RDP/SSH to the internet. Install **Tailscale** on the PC, your client devices, and the Pi; it builds a WireGuard mesh where each device gets a 100.x.x.x address reachable without opening a single inbound port, with NAT traversal handled for you and end-to-end encryption (Tailscale’s coordination server never sees your traffic). Add MagicDNS for friendly names,  optionally disable key-expiry on the always-on PC/Pi, and use Tailscale ACLs to limit which devices can reach the PC. Bind NoMachine/RDP to the Tailscale interface only.

**(b) Secrets on Windows.** Store git credentials in **Git Credential Manager** (ships with Git for Windows, backed by Windows Credential Manager). Use `gh auth login` for GitHub token storage. Keep API keys (Anthropic/OpenAI for the agents) in environment variables or a secrets manager, never in committed `.env` — gitignore all `.env*` and keep a committed `.env.example`. Windows Credential Manager is the OS-level vault for anything else.

**(c) Supply-chain tools.** gitleaks, Trivy, Syft, and Grype all run as native Windows binaries. Wire them into your `security` task: `gitleaks` (secrets), `trivy fs` (deps/vulns/secrets/IaC in one binary — simplest), and/or `syft` → `grype` (SBOM-then-scan).  Add language-native scanners: `cargo audit`, `pip-audit`/uv-based audit, `govulncheck`. Trivy-in-one-binary is the pragmatic default for a solo founder.

**(d) Defender exclusions tradeoff (restated honestly).** The §2a exclusions are a real security reduction: excluded paths aren’t scanned in real time, so a malicious dependency dropped into your project or cache directory won’t be caught there. This is an accepted, deliberate tradeoff for build speed — offset it by keeping real-time protection ON everywhere else, scoping exclusions narrowly, and relying on the supply-chain scanners above to cover the excluded dev paths.

## Recommendations (staged “do this first” launch plan)

**Tomorrow (first 60-90 minutes, highest ROI):**

1. **Defender exclusions** (§2a) — run the PowerShell block. Biggest single build-speed win.
1. **Long paths** — registry `LongPathsEnabled=1` + `git config --system core.longpaths true`, then reboot (§2b). Prevents worktree/node_modules/target failures.
1. **`.gitattributes` + renormalize** in each active repo (§2c); set `core.autocrlf=false`, `core.fileMode=false` globally. Prevents Windows↔Pi line-ending churn.
1. **git perf**: `git config --global core.fsmonitor true` and `git config --global core.untrackedcache true`. GitHub’s engineering benchmark on large repos (Chromium ~400K files, plus synthetic 1M/2M-file repos) found commands that “took from 17 to 85 seconds” without FSMonitor “took less than 1 second” with it enabled. Caveat: if a shell prompt shows stale status, that’s the known fsmonitor+prompt interaction — refresh or disable per-repo.
1. **Developer Mode ON** + `core.symlinks true`; stop committing `.venv` symlinks — gitignore `.venv`, recreate via `uv sync` (§2e).
1. **Confirm `C:\Projects\MatrymLabs` is NOT inside OneDrive** (§4c).

**This week:**
7. **Install the toolchain via winget** using the verified IDs (§3a); write a `.winget/configuration.dsc.yaml` into a `machine-bootstrap` repo so the machine is reproducible.
8. **Fix the JDK mismatch**: add `foojay-resolver-convention` v1.0.0 + toolchain block to RetroForge’s Gradle build, pin JDK 21 (§3b/§6d). Install Temurin 21 + 24 via winget as the base.
9. **fnm for Node** (§3c); reinstall Claude Code’s npm under the fnm-managed Node.
10. **Set parallelism flags**: `addopts = -n auto` in pyproject, `org.gradle.parallel=true`+caching in gradle.properties (§5a).
11. **Tailscale** on PC + Pi + laptop; stop any port-forwarding (§7a). Bind NoMachine to the Tailscale interface.

**Next 1-2 weeks:**
12. **Migrate Makefile → Taskfile.yml** keeping target names `lint/typecheck/test/security/mutation/build` (§6a).
13. **CI matrix**: add `windows-latest` alongside `ubuntu-latest` for core checks; keep the Pi as ARM smoke-test (§6b).
14. **pre-commit**: audit for bash hooks, rewrite as PowerShell/Python, add Windows-safety hooks (§6c).
15. **Optional 4090 local-LLM rig**: Ollama + Qwen3-Coder 32B (Q4_K_M) + an embedder, as a supplement to Claude Code/Codex for bulk/private tasks — timeboxed (§5c/d).

**Benchmarks / thresholds that would change these:**

- If `git status` on your largest repo is still >2s after FSMonitor, add `feature.manyFiles=true` and check for an unignored build dir.
- If Rust/Gradle builds are RAM-starved (swapping) at full parallelism, cap `CARGO_BUILD_JOBS`/`org.gradle.workers.max`.
- If profiling shows disk I/O (not AV/CPU) as the bottleneck, *then* revisit a RAM disk (§5b).
- If you ever move Rider itself into WSL2 (Linux Rider + Linux agents), the native-Windows ruling flips — but that abandons Godot/NoMachine ergonomics, so it’s not recommended.

## What changes from your existing per-language reference (Windows deltas)

- **uv/ruff/mypy/pytest:** unchanged commands; add `-n auto` and Defender/index exclusions. `.venv` must be gitignored (no committed symlinks).
- **clippy/rustfmt (cargo):** unchanged; use MSVC toolchain; exclude `.cargo`/`.rustup`/`target` from Defender; long paths mandatory for `target/`.
- **golangci-lint:** unchanged; exclude `go` cache from Defender.
- **gdtoolkit/gdunit4:** gdtoolkit via uv; Godot native Windows build; the 4090 helps the editor/rendering.
- **Makefile-orchestrated checks:** **this is the biggest change — migrate to Taskfile.yml (Task).** Same target names, YAML instead of tab-sensitive Make, no bash dependency.
- **JDK/Gradle:** add foojay toolchain resolver + pinned `languageVersion`; manage JDKs via winget + (optionally) mise, not SDKMAN.

## Caveats

- **Speed figures are workload-dependent.** The WSL2 “~6% of native / 10-20x slower” numbers come from community benchmarks (Takken, How-To Geek, Lorbic) and one-off `dd`/git tests, not a controlled study of your repos; the direction is robust and corroborated across many sources, but your exact multipliers will vary. The FSMonitor “17-85s → <1s” figure is GitHub’s measurement on very large repos (Chromium/synthetic million-file repos) — your 13 repos are smaller, so expect a proportionally smaller (still real) win. Defender-exclusion speedups are reported qualitatively (JetBrains, Microsoft) rather than as a single reliable percentage.
- **Local-LLM tok/s and benchmark claims** (Qwen3-Coder 32B ~48-54 tok/s, 71.4% SWE-bench) come from vendor-published figures and third-party benchmark sites (BestLLMfor, ModelFit, Morph) — treat as indicative, not audited. Model recommendations move fast; re-check the current best 24 GB coding model before committing.
- **WinGet Configuration (DSC)** is documented by Microsoft as the supported reproducible mechanism and requires WinGet 1.6.2631+, but Microsoft’s docs don’t explicitly stamp it “GA,” and the underlying DSC resource modules are still maturing — validate your config file and pin resource versions.
- **winget package IDs** were verified against winget-pkgs/vendor docs as of this research, but IDs and manifest availability (especially Tailscale’s architecture handling on ARM) can change; run `winget search` to confirm before scripting.
- **rustup under winget** can’t be version-tracked by winget; manage it with `rustup` itself.
- This baseline assumes Windows 11 (your stated OS) and a Pro/Enterprise edition for full RDP-host and Group Policy options; Home edition lacks RDP hosting (use NoMachine/Tailscale instead) and some policy toggles.