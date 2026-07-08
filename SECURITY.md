# Security Policy

## Reporting a vulnerability

Please open a private [security advisory](https://github.com/MatrymLabs/codeforge/security/advisories/new)
on GitHub, or email the maintainer. Do not file public issues for suspected
vulnerabilities.

## Design notes

CodeForge authenticates accounts with salted pbkdf2-sha256 (600,000 iterations,
constant-time comparison) and returns generic login refusals to prevent user
enumeration. Telnet IAC negotiation masks passwords at the front desk. A full
threat model and hardening roadmap live in
[docs/reports/security/](docs/reports/security/).

## Supported versions

This is a portfolio project; `main` is the only supported line.
