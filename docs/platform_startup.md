# CodeForge platform startup

The product startup contract is implemented by the Master Client's `codeforge` entry point and
the Engine subsystem's `adapters.cli.main()` together with
`kernel.platform.bootstrap_platform()`. The Engine CLI resolves the Seed before importing the
world. The bootstrap then initializes the existing configuration, identity, persistence,
Hardware Store, isolated R&D audit, Engine, Seed Runtime, Creator Workshop, and operational
API boundary before importing a serving or play driver.

```mermaid
flowchart TD
    USER[User]
    CODEFORGE[CodeForge Unified Product Platform]
    CLIENT[CodeForge Master Client]
    SERVICES[CodeForge Platform Services]
    ENGINE[CodeForge Engine and Seed Runtime]
    AETHRYN[Aethryn Bundled Flagship Seed]
    OTHERSEEDS[Other CodeForge Seeds]
    CREATOR[Creator Workshop]
    CONSOLE[Creator Console]
    STORE[Hardware Store]
    RND[R&D Tech Lab]
    TESTS[Validation and Testing]
    TARGETS[Target Products]
    OBSERVE[Logs Metrics Feedback]

    USER --> CODEFORGE
    CODEFORGE --> CLIENT
    CLIENT --> SERVICES
    CLIENT --> ENGINE
    SERVICES --> ENGINE
    SERVICES --> STORE
    SERVICES --> RND
    SERVICES --> CONSOLE
    ENGINE --> AETHRYN
    ENGINE --> OTHERSEEDS
    ENGINE --> CREATOR
    RND --> TESTS
    TESTS --> STORE
    STORE --> ENGINE
    STORE --> CREATOR
    STORE --> AETHRYN
    STORE --> OTHERSEEDS
    CREATOR --> RND
    CREATOR --> STORE
    ENGINE --> TARGETS
    TARGETS --> OBSERVE
    AETHRYN --> OBSERVE
    OTHERSEEDS --> OBSERVE
    OBSERVE --> RND
```

The read-only runtime projection is available at `GET /api/platform/status`. It is the
contract intended for the Master Client and Creator Console; protected operations still use
the existing server-side authorization boundary.

The Engine library retains its historical direct-import default for compatibility. Product
startup resolves Aethryn by default and sets `FORGE_SEED` before the world is imported. An
invalid explicit, active-project, persisted, or environment selection fails clearly and does
not silently substitute another Seed.
