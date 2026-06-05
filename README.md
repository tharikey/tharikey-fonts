# tharikey-fonts

The font catalog for **ThariKey**. Per-foundry YAML is compiled into one schema-validated `manifest.json`,
deployed to Cloudflare R2 behind `fonts.tharikey.com`, and consumed by the macOS app and the website.

## Layout

```
foundries/<foundry>/
  meta.yaml      # foundry: id, name, url, logo, defaultLicense, defaultTier, defaultDesigner
  catalog.yaml   # the foundry's families (the file you edit)
  assets/        # font binaries, logo, previews → pushed to R2
licenses.yaml    # license registry (id → name, url)
schema/manifest.schema.json   # the contract
tools/build_manifest.py       # compile: YAML → dist/manifest.json
dist/manifest.json            # built artifact (gitignored; CI builds + deploys)
```

## Build

```sh
python3 tools/build_manifest.py          # → dist/manifest.json
python3 tools/build_manifest.py --check  # validate only (CI gate)
```

## The manifest

Top-level `licenses` and `foundries` registries; each family references them by id. Keys are camelCase in
both the YAML and the JSON. Full contract in `schema/manifest.schema.json`.

A family's downloads (`files[]`) come in three modes:

| mode | declare | result |
|---|---|---|
| we-host | `label` + `format`, binary in `assets/` | compiler hosts on R2, stamps `url`/`sha256`/`bytes` |
| foundry-host | explicit `url` | served from their CDN (their download telemetry) |
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
`descriptionDv`, `copyright`, `version`, `updated`.

### Crawlers (optional)

A foundry catalog may be *generated* by a crawler instead of hand-written — see `tools/crawl_thaana.py` as
a reference. Rules:

- A crawler is a **sourcing tool, never part of the build.** Run it, **review the diff, and commit the
  generated `catalog.yaml`** — the build only ever reads the committed YAML.
- Keep the crawler in `tools/` so it can be re-run and referenced.
