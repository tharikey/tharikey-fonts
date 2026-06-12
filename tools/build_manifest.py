#!/usr/bin/env python3
"""Compile the per-foundry meta.yaml + catalog.yaml fragments into dist/manifest.json.

Sources own the truth (foundries/<foundry>/{meta,catalog}.yaml + assets/); this aggregates + validates
them into the single artifact the macOS app and the website consume. Hosting (R2 push) and previews
(screenshots) are deferred seams: we-host file URLs / sha256 / bytes stay null until a binary is vendored.

Keys are camelCase in both the fragments and the manifest (no mapping layer — friendliest for the Swift
and JS consumers). Licenses + foundries are top-level registries; families reference them by id.

Usage:
  python3 tools/build_manifest.py [--check] [--base-url https://fonts.tharikey.com]
"""
from __future__ import annotations

import argparse
import datetime
import hashlib
import json
import sys
from pathlib import Path

try:
    import yaml
except ImportError:
    sys.exit("error: PyYAML is required — `pip install -r requirements.txt`")

ROOT = Path(__file__).resolve().parent.parent
FOUNDRIES = ROOT / "foundries"
SCHEMA = ROOT / "schema" / "manifest.schema.json"
OUT = ROOT / "dist" / "manifest.json"          # pretty — for diffing/inspection
OUT_MIN = ROOT / "dist" / "manifest.min.json"  # compact — what consumers fetch
SCHEMA_VERSION = 1
EXT = {"TTF": "ttf", "OTF": "otf", "WOFF2": "woff2"}

warnings: list[str] = []


def warn(msg: str) -> None:
    warnings.append(msg)


def load_yaml(path: Path) -> dict:
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def build_files(assets: Path, fam_files: list, fid: str, foundry_id: str, base_url: str) -> list[dict]:
    out = []
    for entry in fam_files:
        label = entry["label"]
        fmt = entry.get("format", "TTF")
        archive = entry.get("archive")  # "zip" | None
        if entry.get("url"):
            # Foundry-hosted (e.g. thaana's per-format .zip) — we don't serve it; their telemetry.
            out.append({"label": label, "format": fmt, "archive": archive,
                        "url": entry["url"], "sha256": entry.get("sha256"), "bytes": entry.get("bytes")})
            continue
        # We host: a clean, bracket-free canonical name decoupled from the upstream filename.
        ext = "zip" if archive == "zip" else EXT.get(fmt, fmt.lower())
        canonical = f"{fid}-{label.lower()}.{ext}"
        blob = assets / canonical
        if blob.is_file():
            data = blob.read_bytes()
            out.append({"label": label, "format": fmt, "archive": archive,
                        "url": f"{base_url.rstrip('/')}/{foundry_id}/{canonical}",
                        "sha256": hashlib.sha256(data).hexdigest(), "bytes": len(data)})
        else:
            warn(f"{foundry_id}/{fid}: '{canonical}' not vendored in assets/ — url/sha256/bytes null")
            out.append({"label": label, "format": fmt, "archive": archive,
                        "url": None, "sha256": None, "bytes": None})
    return out


def build_previews(assets: Path, fid: str, foundry_id: str, base_url: str, raw: dict) -> list[str]:
    """Previews are derived by convention: a `<id>-specimen*.png` vendored in the foundry's assets/ IS
    that family's preview (rendered by build_specimens.py for our/free fonts, or dropped by hand for a
    foundry-supplied premium specimen). Any explicit URLs in the catalog `previews:` pass through first."""
    out: list[str] = list(raw.get("previews") or [])
    if assets.is_dir():
        for png in sorted(assets.glob(f"{fid}-specimen*.png")):
            out.append(f"{base_url.rstrip('/')}/{foundry_id}/{png.name}")
    return out


def build_family(raw: dict, foundry: dict, assets: Path, used_licenses: set, base_url: str) -> dict:
    fid = raw["id"]
    where = f"{foundry['id']}/{fid}"
    tier = raw.get("tier", foundry.get("defaultTier"))
    if tier not in ("free", "premium"):
        sys.exit(f"error: {where}: tier must be 'free' or 'premium' (set it, or foundry defaultTier)")
    license_id = raw.get("license", foundry.get("defaultLicense"))
    if not license_id:
        sys.exit(f"error: {where}: no license (set family.license or foundry.defaultLicense)")
    used_licenses.add(license_id)

    fam = {
        "id": fid,
        "name": raw["name"],
        "nameDv": raw.get("nameDv"),
        "foundry": foundry["id"],
        "designer": raw.get("designer", foundry.get("defaultDesigner", foundry["name"])),
        "copyright": raw.get("copyright"),
        "description": raw.get("description", ""),
        "descriptionDv": raw.get("descriptionDv"),
        "tier": tier,
        "license": license_id,
        "category": raw.get("category", []),
        "version": str(raw["version"]) if raw.get("version") is not None else None,
        "updated": str(raw["updated"]) if raw.get("updated") is not None else None,
        "variable": bool(raw.get("variable", False)),
        "weights": int(raw.get("weights", 1)),
        "formats": raw.get("formats", ["TTF"]),
        "files": [],
        "purchaseUrl": None,
        "homepage": raw.get("homepage"),
        "previews": build_previews(assets, fid, foundry["id"], base_url, raw),
    }

    if tier == "free":
        if raw.get("purchaseUrl"):
            sys.exit(f"error: {where}: a free family must not declare purchaseUrl")
        if not raw.get("files"):
            sys.exit(f"error: {where}: a free family must declare files[]")
        fam["files"] = build_files(assets, raw["files"], fid, foundry["id"], base_url)
    else:  # premium
        if raw.get("files"):
            sys.exit(f"error: {where}: a premium family must not host files[] (link out instead)")
        fam["purchaseUrl"] = raw.get("purchaseUrl") or foundry.get("url")
        if not fam["purchaseUrl"]:
            sys.exit(f"error: {where}: a premium family needs purchaseUrl (or foundry.url)")
    return fam


def resolve_logo(meta: dict, assets: Path, foundry_id: str, base_url: str) -> str | None:
    logo = meta.get("logo")
    if not logo:
        return None
    if (assets / logo).is_file():
        return f"{base_url.rstrip('/')}/{foundry_id}/{logo}"
    warn(f"{foundry_id}: logo '{logo}' not in assets/ — left null")
    return None


def build_bundle(raw: dict, foundry_id: str | None, fam_foundry: dict, seen: set) -> dict:
    """A bundle is a curated list of existing family ids — validated, never new fonts."""
    bid = raw["id"]
    where = f"bundle '{bid}'" + (f" ({foundry_id})" if foundry_id else "")
    if bid in seen:
        sys.exit(f"error: duplicate bundle id '{bid}'")
    seen.add(bid)
    fams = raw.get("families") or []
    if not fams:
        sys.exit(f"error: {where}: must list at least one family")
    for fid in fams:
        if fid not in fam_foundry:
            sys.exit(f"error: {where}: references unknown family '{fid}'")
        if foundry_id and fam_foundry[fid] != foundry_id:
            sys.exit(f"error: {where}: references '{fid}' from another foundry "
                     f"('{fam_foundry[fid]}') — only root bundles.yaml may mix foundries")
    return {
        "id": bid, "name": raw["name"], "nameDv": raw.get("nameDv"),
        "description": raw.get("description", ""), "descriptionDv": raw.get("descriptionDv"),
        "foundry": foundry_id, "families": fams, "featured": bool(raw.get("featured", False)),
    }


def build(base_url: str) -> dict:
    registry = load_yaml(ROOT / "licenses.yaml")
    foundries, families, used_licenses, seen_ids = [], [], set(), set()
    raw_bundles: list = []  # (raw_bundle, foundry_id | None)

    for fdir in sorted(p for p in FOUNDRIES.iterdir() if p.is_dir()):
        meta = load_yaml(fdir / "meta.yaml")
        if meta.get("id") != fdir.name:
            warn(f"foundry '{meta.get('id')}' does not match its folder '{fdir.name}'")
        assets = fdir / "assets"
        foundries.append({
            "id": meta["id"], "name": meta["name"], "nameDv": meta.get("nameDv"),
            "url": meta.get("url"), "description": meta.get("description", ""),
            "descriptionDv": meta.get("descriptionDv"),
            "logo": resolve_logo(meta, assets, meta["id"], base_url),
        })
        catalog = load_yaml(fdir / "catalog.yaml")
        for raw in catalog.get("families", []):
            fam = build_family(raw, meta, assets, used_licenses, base_url)
            if fam["id"] in seen_ids:
                sys.exit(f"error: duplicate family id '{fam['id']}'")
            seen_ids.add(fam["id"])
            families.append(fam)
        for rb in catalog.get("bundles", []):  # a foundry's own bundles
            raw_bundles.append((rb, meta["id"]))

    # Cross-foundry collections we curate (may mix foundries).
    if (ROOT / "bundles.yaml").exists():
        for rb in load_yaml(ROOT / "bundles.yaml").get("bundles", []):
            raw_bundles.append((rb, None))

    licenses = []
    for lid in sorted(used_licenses):
        lic = registry.get(lid)
        if lic is None:
            sys.exit(f"error: license id '{lid}' referenced but not in licenses.yaml")
        licenses.append({"id": lid, "name": lic["name"], "url": lic.get("url")})

    fam_foundry = {f["id"]: f["foundry"] for f in families}
    bundles, seen_bundle_ids = [], set()
    for rb, foundry_id in raw_bundles:
        bundles.append(build_bundle(rb, foundry_id, fam_foundry, seen_bundle_ids))

    return {
        "version": SCHEMA_VERSION,
        "generatedAt": datetime.date.today().isoformat(),
        "licenses": licenses,
        "foundries": foundries,
        "families": families,
        "bundles": bundles,
    }


def validate(manifest: dict) -> None:
    try:
        import jsonschema
    except ImportError:
        warn("jsonschema not installed — skipped schema validation")
        return
    jsonschema.validate(manifest, json.loads(SCHEMA.read_text(encoding="utf-8")))


def main() -> None:
    ap = argparse.ArgumentParser(description="Compile the ThariKey font manifest.")
    ap.add_argument("--check", action="store_true", help="validate only; do not write")
    ap.add_argument("--base-url", default="https://fonts.tharikey.com", help="CDN/R2 base for hosted files")
    args = ap.parse_args()

    manifest = build(args.base_url)
    validate(manifest)
    for w in warnings:
        print(f"  warn: {w}", file=sys.stderr)

    n_free = sum(1 for f in manifest["families"] if f["tier"] == "free")
    summary = (f"{len(manifest['foundries'])} foundries, {len(manifest['licenses'])} licenses, "
               f"{len(manifest['families'])} families ({n_free} free, {len(manifest['families']) - n_free} premium), "
               f"{len(manifest['bundles'])} bundles")
    if args.check:
        print(f"ok: manifest valid — {summary}")
        return
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    OUT_MIN.write_text(json.dumps(manifest, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    print(f"wrote {OUT.relative_to(ROOT)} + {OUT_MIN.name} — {summary}")


if __name__ == "__main__":
    main()
