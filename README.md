# tharikey-fonts

The **font catalog** for ThariKey — a versioned manifest the macOS app's `FontCatalogService` and the
[tharikey.com](https://tharikey.com) website consume, plus the OFL font files we host ourselves.

## How it works

Sources own their truth; the manifest is a **built artifact**. Each foundry has one folder with a `meta`
file, a `catalog` of all its families, and a single `assets/` bucket. A Python build step aggregates +
validates every fragment into one `dist/manifest.json`.

```
foundries/
  <foundry>/
    meta.yaml                 # foundry: id, name(+nameDv), url, description, logo, defaultLicense, defaultTier
    catalog.yaml             # ALL families in one list — the file a contributor edits
    assets/                  # one bucket: font binaries, logo, (later) previews → pushed to R2
licenses.yaml                 # license registry (id → name + url) — where licenses live
schema/manifest.schema.json   # the versioned contract (app + site validate against this)
tools/build_manifest.py       # the compiler  (R2-push + screenshot-gen land here later)
tools/crawl_thaana.py         # sourcing: scrape thaana.com → regenerate its catalog.yaml
dist/manifest.json            # the built artifact (served from R2)
```

## Sourcing (crawl)

thaana.com has ~19 OFL families, each on a detail page with per-format `.zip`s. Rather than hand-maintain
them, `tools/crawl_thaana.py` scrapes the site and **regenerates `foundries/thaana/catalog.yaml`**, linking
each family to thaana's own `.zip` (foundry-hosted → their download telemetry; `archive: zip` tells the app
to unpack + register). It's a *sourcing* step, kept out of the build: run it where there's network, then
**review the diff** before committing — so the build stays deterministic and a page-structure change can't
silently corrupt the manifest.

```sh
pip install requests beautifulsoup4 pyyaml
python3 tools/crawl_thaana.py        # → rewrites foundries/thaana/catalog.yaml (review the diff!)
```

**Top-level registries, referenced by id** (same pattern for both): `licenses` and `foundries` are
top-level lists; each family points at them by id (`license: OFL-1.1`, `foundry: thaana`). Keys are
camelCase in both the fragments and the manifest — no mapping layer for the Swift/JS consumers.

**Hosting — two modes per file:**
- **We host** (free OFL fonts): the catalog declares a file by `style`+`format` only. The compiler derives
  a clean canonical name (`bolhu-variable.ttf`), expects that binary in `assets/`, and stamps
  `url`+`sha256`+`bytes` (null until vendored). No upstream `[wght]`-style brackets in any URL.
- **Foundry hosts**: the file gives an explicit `url:` (their CDN — keeps download telemetry theirs). We
  don't serve it; `sha256`/`bytes` are optional.

**Licenses & attribution** live in three places, by design: license *definitions* in `licenses.yaml`
(the registry); per-family *attribution* (`copyright`, `designer`) on the family; and for OFL fonts we
host, the license *text* (`OFL.txt`) travels in `assets/` and ships to R2 alongside the fonts (OFL
compliance). The manifest's `license` id resolves to `{id,name,url}` via the top-level registry.

**Invariants the build enforces:**

- `tier: free` ⇒ has `files[]`, **no** `purchaseUrl` (we host, or the foundry hosts, the OFL fonts).
- `tier: premium` ⇒ has `purchaseUrl`, **no** hosted `files[]` (we never host commercial fonts; we link out).
- Every `license` / `defaultLicense` resolves against `licenses.yaml`; ids are unique.

## Build

```sh
python3 tools/build_manifest.py            # → dist/manifest.json
python3 tools/build_manifest.py --check    # validate only, no write (CI)
```

## Hosting (deferred)

- **Free (OFL) fonts** → we host. `tools/` will gain an R2-push command that uploads each `files/` blob to
  Cloudflare R2 and the build stamps the resulting URL + `sha256` + `bytes` into the manifest.
- **Premium fonts** → never hosted; the manifest carries only the foundry's `purchaseUrl`.
- **Previews** → a screenshot tool will render specimens into `previews/` and stamp their URLs in.

Both are seams in the schema today (`files[].url/sha256/bytes` may be null until hosted; `previews` may be
empty) so the contract is stable now and the tooling fills it in later.
