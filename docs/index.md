---
title: "Font catalog"
---

ThariKey's font catalog is a **published manifest** — a single JSON file listing the Thaana font families
and curated collections available in the app, with where to get each one. It's compiled from per-foundry
YAML in this repo and served as a static file; clients (the macOS app, the website) fetch it directly.

- **[Manifest format](manifest.md)** — the contract: registries, family fields, download modes, bundles.
- **[Authoring](authoring.md)** — add a foundry, a family, or a collection.

## How a font reaches a user

1. A foundry's families are described in YAML (`foundries/<id>/catalog.yaml`).
2. The build compiles + schema-validates every fragment into `manifest.json` (+ a minified
   `manifest.min.json` that clients fetch).
3. The app reads the manifest, shows the catalog, and installs a family on demand.

## Hosting modes

A family's download is one of three modes — the manifest says which, and the app does the right thing:

| mode | what | install |
|---|---|---|
| **we-host** | an OFL font we serve | the app downloads + registers it |
| **foundry-host** | the foundry serves the file (their CDN / download telemetry) | the app downloads from their URL + registers it |
| **premium** | a commercial font we never host | the app links out to the foundry to purchase |

Free fonts (OFL or foundry-hosted) install in place; premium fonts link out. Everything is data in the
manifest — adding a foundry or a font is a YAML change, no code.
