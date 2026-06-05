# tharikey-fonts

The font catalog for **ThariKey** — the source of truth for the font manifest. Per-foundry YAML is
compiled into one schema-validated `manifest.json` that downstream clients fetch.

> Reference docs — [manifest format](docs/manifest.md) and [authoring](docs/authoring.md) — live in [`docs/`](docs/).

## Layout

```
foundries/<foundry>/
  meta.yaml      # foundry: id, name, url, logo, defaultLicense, defaultTier, defaultDesigner
  catalog.yaml   # the foundry's families (+ optional bundles) — the file you edit
  assets/        # font binaries, logo, previews
bundles.yaml     # cross-foundry collections we curate
licenses.yaml    # license registry (id → name, url)
schema/manifest.schema.json   # the contract
tools/build_manifest.py       # compile: YAML → dist/manifest{,.min}.json
dist/                         # built artifacts (gitignored; built + shipped by CI)
```

## Build

```sh
python3 tools/build_manifest.py          # → dist/manifest.json + dist/manifest.min.json
python3 tools/build_manifest.py --check  # validate only (CI gate)
```

Two files are emitted: **`manifest.json`** (pretty — for diffing/inspection) and **`manifest.min.json`**
(compact — what consumers fetch).

## The manifest

Top-level `licenses`, `foundries`, and `bundles` registries; families reference them by id. Keys are
camelCase in both the YAML and the JSON. Full contract in `schema/manifest.schema.json`.

A family's downloads (`files[]`) come in three modes:

| mode | declare | result |
|---|---|---|
| we-host | `label` + `format`, binary in `assets/` | compiler hosts it, stamps `url`/`sha256`/`bytes` |
| foundry-host | explicit `url` | served from the foundry (their download telemetry) |
| premium | `tier: premium` + `purchaseUrl`, no `files` | link out; never hosted |

`archive: zip` marks an archive download — the app unpacks it and registers the font(s) inside.

## Contributing

### Add a foundry

1. `foundries/<id>/meta.yaml` — `id`, `name`, `url`, `defaultLicense`, `defaultTier` (+ optional `logo`,
   `defaultDesigner`, `nameDv`).
2. `foundries/<id>/catalog.yaml` — the families (below).
3. Put any `logo` / we-hosted binaries in `foundries/<id>/assets/`; add a new license to `licenses.yaml`.
4. `python3 tools/build_manifest.py --check`, then open a PR.

### A family entry

```yaml
families:
  - id: bolhu
    name: Bolhu
    description: A variable Thaana grotesk in 9 weights.
    category: [sans]          # sans | serif | display | monospace | handwriting
    variable: true
    weights: 9
    files: [{ label: Variable, format: TTF, archive: zip, url: "https://…/Bolhu-vf.zip" }]
```

`tier`, `license`, and `designer` inherit the foundry's `default*` unless set. **Premium:** drop `files`,
add `purchaseUrl`. **We-host:** omit `url` and drop the binary in `assets/`. Optional: `nameDv`,
`descriptionDv`, `copyright`, `version`, `updated`, `homepage`.

### Bundles (collections)

A bundle is a curated **list of family ids** — not new fonts. The app shows it as a card and offers
install-all or install-individual. Author in one of two places:

- **Cross-foundry (ours)** → root `bundles.yaml`:
  ```yaml
  bundles:
    - id: essentials
      name: Essentials
      description: A workhorse set — text, UI, mono, display.
      families: [bolhu, kolhu, masnooee-mono, theras]   # any foundry
      featured: true
  ```
- **A foundry's own** → a `bundles:` key in its `catalog.yaml` (the `foundry` is inherited; reference
  only that foundry's families):
  ```yaml
  bundles:
    - id: thaana-complete
      name: Thaana.com Complete
      families: [bolhu, kolhu, theras, …]
  ```

The build validates every referenced family id exists, bundle ids are unique, and a foundry bundle only
references its own families.

### Crawlers (optional)

A foundry catalog may be *generated* by a crawler instead of hand-written — see `tools/crawl_thaana.py` as
a reference. Rules:

- A crawler is a **sourcing tool, never part of the build.** Run it, **review the diff, and commit the
  generated `catalog.yaml`** — the build only ever reads the committed YAML.
- Keep the crawler in `tools/` so it can be re-run and referenced.
