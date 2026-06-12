---
title: "Manifest format"
---

The compiled catalog (`manifest.json`). The authoritative contract is
[`schema/manifest.schema.json`](https://github.com/tharikey/tharikey-fonts/blob/main/schema/manifest.schema.json);
this page is the readable companion. Keys are camelCase in both the YAML and the JSON.

## Shape

```jsonc
{
  "version": 1,                 // schema version — clients check it
  "generatedAt": "2026-06-05",
  "licenses":  [ /* License */ ],   // registry; families reference by id
  "foundries": [ /* Foundry */ ],   // registry; families reference by id
  "families":  [ /* FontFamily */ ],
  "bundles":   [ /* Bundle */ ]     // curated collections (lists of family ids)
}
```

`licenses`, `foundries`, and `bundles` are **top-level registries**. Families point at a license and a
foundry **by id**, so a license/foundry is defined once and never duplicated.

## Family

```jsonc
{
  "id": "bolhu", "name": "Bolhu", "nameDv": null,
  "foundry": "thaana",            // → foundries[].id
  "designer": "…", "copyright": null,
  "description": "…", "descriptionDv": null,
  "tier": "free",                 // "free" | "premium"
  "license": "OFL-1.1",           // → licenses[].id
  "category": ["sans"],           // sans | serif | display | monospace | handwriting
  "version": "1.0", "updated": null,
  "variable": true, "weights": 9, "formats": ["TTF"],
  "files": [ /* File */ ],        // free: how to download
  "purchaseUrl": null,            // premium: where to buy (no files)
  "homepage": "https://thaana.com/bolhu/",   // the family's page on the foundry site (nullable)
  "previews": ["https://…/thaana/bolhu-specimen.png"]   // specimen image URLs
}
```

Nullable everywhere it makes sense (`nameDv`, `copyright`, `version`, `homepage`, …); the key is always
present so the shape is stable.

**`previews` is derived by convention** — a `<id>-specimen*.png` vendored in a foundry's `assets/`
becomes that family's preview URL (the build stamps the hosted URL, like it does for `files`). For our
own + free fonts, `tools/build_specimens.py` renders those PNGs from the actual font (dev-local, via
`hb-view`); for premium fonts the foundry supplies the image and you drop it into `assets/` by hand.
Explicit URLs in a catalog `previews:` list pass through too.

### File (a download)

```jsonc
{ "label": "Variable", "format": "TTF", "archive": "zip",
  "url": "https://thaana.com/bolhu/Bolhu-vf.zip", "sha256": null, "bytes": null }
```

- `archive: "zip"` → the download is an archive; the client unpacks it and registers the font(s) inside.
  `null` → `url` is the font file itself.
- **we-host:** `url`/`sha256`/`bytes` are stamped by the build. **foundry-host:** `url` is the foundry's
  own; `sha256`/`bytes` may be null.

## Bundle

A curated collection — a list of existing family ids, not new fonts. The app shows it as a card and
offers install-all or install-individual.

```jsonc
{ "id": "essentials", "name": "Essentials", "nameDv": null,
  "description": "…", "descriptionDv": null,
  "foundry": null,                // a foundry's own bundle sets this; null = cross-foundry curation
  "families": ["bolhu", "kolhu", "masnooee-mono", "theras"],
  "featured": true }
```

## License

```jsonc
{ "id": "OFL-1.1", "name": "SIL Open Font License 1.1", "url": "https://openfontlicense.org" }
```
