## Summary

What problem does this change solve?

## Card

- [ ] New/changed part has a `CARD:` docstring
- [ ] Test twin added or updated
- [ ] New commands have an engine-tick test

## How to verify

1. `make check`
2.

## Risk

- [ ] Low  - [ ] Medium  - [ ] High

## Disclosure (AI-assisted delivery)

Mark what applies. These feed the tamper-evident delivery ledger (Human-Keel transparency +
the FWA audit-ledger discipline); an honest answer is the whole point.

- [ ] `ai_assisted` - AI helped author this change
- [ ] `security_sensitive` - touches auth, secrets, crypto, the gateway, or a security gate
- [ ] `new_dependencies` - adds or changes a runtime/dev dependency
- [ ] `secrets_or_config` - changes secrets handling or configuration

## Checklist

- [ ] `make check` green locally
- [ ] Conventional commit message
- [ ] Seeds/docs updated if behavior changed
- [ ] No save files or secrets in the diff
