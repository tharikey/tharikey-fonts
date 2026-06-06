---
title: "Authoring"
---

Everything is YAML compiled by `tools/build_manifest.py`. Run `python3 tools/build_manifest.py --check`
before opening a PR — it schema-validates and **hard-errors** on the mistakes that would poison the
manifest (duplicate ids, an unknown family reference, a foundry bundle reaching into another foundry).

## Add a foundry

```
foundries/<id>/
  meta.yaml      # id, name, url, defaultLicense, defaultTier (+ optional logo, defaultDesigner, nameDv)
  catalog.yaml   # families (+ optional bundles)
  assets/        # logo, we-hosted font binaries
```

A new license goes in the root `licenses.yaml` registry; families reference it by id.

## Add a family

```yaml
# foundries/<id>/catalog.yaml
families:
  - id: bolhu
    name: Bolhu
    description: A variable Thaana grotesk in 9 weights.
    category: [sans]              # sans | serif | display | monospace | handwriting
    variable: true
    weights: 9
    files: [{ label: Variable, format: TTF, archive: zip, url: "https://…/Bolhu-vf.zip" }]
```

`tier`, `license`, and `designer` inherit the foundry's `default*` unless set. Optional per-family:
`nameDv`, `descriptionDv`, `copyright`, `version`, `updated`, `homepage`.

- **Foundry-hosted** (above): give an explicit `files[].url`.
- **We-host:** omit `url`, drop the binary in `assets/`; the build hosts it and stamps `url`/`sha256`/`bytes`.
- **Premium:** drop `files`, add `purchaseUrl` and `tier: premium`.

## Add a bundle

A bundle is a list of existing family ids. Two homes:

- **Cross-foundry (ours)** → root `bundles.yaml`.
- **A foundry's own** → a `bundles:` key in its `catalog.yaml` (the `foundry` is inherited; reference only
  that foundry's families).

```yaml
bundles:
  - id: essentials
    name: Essentials
    description: A workhorse set — text, UI, mono, display.
    families: [bolhu, kolhu, masnooee-mono, theras]
    featured: true
```

## Crawlers (optional)

A foundry catalog can be **generated** by a crawler rather than hand-written — see `tools/crawl_thaana.py`.

- A crawler is a **sourcing tool, never part of the build**: run it, review the diff, and **commit the
  generated `catalog.yaml`**. The build only ever reads committed YAML, so it stays deterministic and
  offline.
- Keep the crawler in `tools/` for re-runs and reference.
