# Hardware Store loop (this repo consumes from the fleet catalog)

Before building a reusable capability, search the [Matrym Labs Hardware
Store](https://github.com/MatrymLabs/hardware-store) and record the look:

```bash
pip install "matrym-hardware-store @ git+https://github.com/MatrymLabs/hardware-store@v0.2.0"
store-search "<capability>" --repo codeforge --log-file .hardware-store/search_log.jsonl
git add .hardware-store/search_log.jsonl
```

`search_log.jsonl` is committed on purpose: it is the "prove you looked" record the
`consume-first` CI gate reads. If you must reimplement a catalogued capability, write
a `# DECISION:` comment in the file explaining why, and the gate lets it through with
the reason recorded. See the Store's `docs/STREAM_INTEGRATION.md`.
