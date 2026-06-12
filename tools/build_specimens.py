#!/usr/bin/env python3
"""Render Thaana specimen PNGs for catalog families → foundries/<foundry>/assets/<id>-specimen.png.

A DEV-LOCAL sourcing tool, deliberately separate from build_manifest.py (same spirit as crawl_thaana.py):
it touches the network and shells out to `hb-view` to shape Thaana, so it is NOT part of CI. Run it,
review the new PNGs in the diff, and commit them. CI only uploads the committed assets, and
build_manifest.py derives `previews[]` from them by convention (a `<id>-specimen.png` in a foundry's
assets/ IS that family's preview, however it got there).

Where the font to render comes from, per family:
  - a vendored binary in assets/ (we-host, e.g. the `tharikey` foundry) → render straight from it.
  - else files[].url (foundry-hosted, e.g. thaana) → download (cached) + unpack + render.
  - premium (no files[]) → skipped; drop a foundry-supplied specimen image into assets/ by hand.

Downloads are cached under .cache/ keyed by family id + version, so re-runs don't re-fetch; a font
version bump (catalog `version:`) re-downloads automatically. `--refresh` ignores the cache.

Requires: hb-view (`brew install harfbuzz`), plus requests + pyyaml (see requirements.txt).

Usage:
  python3 tools/build_specimens.py                  # every renderable family (skips up-to-date PNGs)
  python3 tools/build_specimens.py --foundry thaana
  python3 tools/build_specimens.py --id bolhu --id kolhu
  python3 tools/build_specimens.py --force          # re-render even if the PNG already exists
  python3 tools/build_specimens.py --refresh        # ignore the download cache (re-fetch)
"""
from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
import time
import zipfile
from pathlib import Path

try:
    import requests
    import yaml
except ImportError:
    sys.exit("error: build_specimens needs `pip install requests pyyaml`")

ROOT = Path(__file__).resolve().parent.parent
FOUNDRIES = ROOT / "foundries"
CACHE = ROOT / ".cache"
UA = {"User-Agent": "tharikey-fonts-specimens (+https://tharikey.com)"}

# A short, representative Thaana sample (HarfBuzz auto-detects Thaana → RTL). Override per family with a
# catalog `specimenText:` if a font needs a different string to show off.
DEFAULT_SAMPLE = "ދިވެހި ތާނަ"
EXT = {"TTF": "ttf", "OTF": "otf", "WOFF2": "woff2"}

# Specimen look: brand-green ink on a BAKED cream tile (not transparent), so the chip is self-contained
# and reads identically on light AND dark cards — a single ink colour on a transparent bg would vanish on
# one theme or the other. Rendered hi-res so it stays crisp when the app scales it down (a single high-DPI
# PNG — remote AsyncImage has no @2x suffix selection). Colours match the brand palette (theme.css).
FONT_SIZE = 96
MARGIN = 28
FOREGROUND = "1f7a5aff"   # brand accent (forest green)
BACKGROUND = "faf7f0ff"   # brand cream paper (baked in → theme-proof)


def load_yaml(path: Path) -> dict:
    if not path.is_file():
        return {}
    with path.open(encoding="utf-8") as f:
        return yaml.safe_load(f) or {}


def pick_file(fam: dict) -> dict | None:
    """The files[] entry to render: a variable build if present, else the first. None = nothing to render
    (premium / link-out family)."""
    files = fam.get("files") or []
    if not files:
        return None
    return next((f for f in files if str(f.get("label", "")).lower() == "variable"), files[0])


def cached_download(url: str, key: str, refresh: bool) -> Path:
    """Download `url` into .cache/downloads/<key><suffix>, reusing the cached copy unless --refresh."""
    dl = CACHE / "downloads"
    dl.mkdir(parents=True, exist_ok=True)
    suffix = Path(url.split("?", 1)[0]).suffix or ".bin"
    dest = dl / f"{key}{suffix}"
    if dest.is_file() and not refresh:
        return dest
    r = requests.get(url, headers=UA, timeout=60)
    r.raise_for_status()
    dest.write_bytes(r.content)
    time.sleep(0.5)  # be polite — only sleeps on an actual fetch (cache hits don't)
    return dest


def font_in(path: Path, variable: bool) -> Path | None:
    """Pick a renderable font file from a dir (unzipped) or accept a font file directly."""
    if path.is_file() and path.suffix.lower() in (".ttf", ".otf"):
        return path
    fonts = sorted(
        p for p in path.rglob("*")
        if p.suffix.lower() in (".ttf", ".otf") and "__MACOSX" not in p.parts
    )
    if not fonts:
        return None
    if variable:  # prefer a variable build (filename hints) when the family is variable
        vf = next((p for p in fonts if any(h in p.name.lower() for h in ("vf", "variable", "["))), None)
        if vf:
            return vf
    # else prefer a plain .ttf over .otf
    return next((p for p in fonts if p.suffix.lower() == ".ttf"), fonts[0])


def resolve_font(fam: dict, foundry_id: str, assets: Path, refresh: bool) -> Path | None:
    """Get a local font file to render for `fam`, or None to skip (premium / unresolved)."""
    entry = pick_file(fam)
    if entry is None:
        return None
    fid = fam["id"]
    archive = entry.get("archive")
    variable = bool(fam.get("variable", False))

    if entry.get("url"):  # foundry-hosted → download (cached by id+version)
        version = str(fam.get("version") or "x").replace("/", "_")
        src = cached_download(entry["url"], f"{fid}-{version}", refresh)
    else:  # we-host → the vendored binary build_manifest expects in assets/
        ext = "zip" if archive == "zip" else EXT.get(entry.get("format", "TTF"), "ttf")
        src = assets / f"{fid}-{str(entry.get('label', '')).lower()}.{ext}"
        if not src.is_file():
            print(f"  warn: {foundry_id}/{fid}: '{src.name}' not vendored in assets/ — skipped",
                  file=sys.stderr)
            return None

    if archive == "zip" or src.suffix.lower() == ".zip":
        out = CACHE / "extracted" / foundry_id / fid
        if out.exists():
            shutil.rmtree(out)
        out.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(src) as z:
            z.extractall(out)
        return font_in(out, variable)
    return font_in(src, variable)


def render(font: Path, out_png: Path, sample: str) -> None:
    out_png.parent.mkdir(parents=True, exist_ok=True)
    subprocess.run(
        ["hb-view", f"--font-size={FONT_SIZE}", f"--margin={MARGIN}",
         f"--foreground={FOREGROUND}", f"--background={BACKGROUND}",
         "--output-format=png", f"--output-file={out_png}", str(font), sample],
        check=True,
    )


def main() -> None:
    if not shutil.which("hb-view"):
        sys.exit("error: hb-view not found — `brew install harfbuzz`")
    ap = argparse.ArgumentParser(description="Render Thaana specimen PNGs into foundry assets/.")
    ap.add_argument("--foundry", help="only this foundry id (e.g. thaana, tharikey)")
    ap.add_argument("--id", action="append", dest="ids", help="only this family id (repeatable)")
    ap.add_argument("--force", action="store_true", help="re-render even if the specimen PNG exists")
    ap.add_argument("--refresh", action="store_true", help="ignore the download cache (re-fetch)")
    args = ap.parse_args()

    want_ids = set(args.ids or [])
    rendered = skipped = failed = 0

    for fdir in sorted(p for p in FOUNDRIES.iterdir() if p.is_dir()):
        if args.foundry and fdir.name != args.foundry:
            continue
        assets = fdir / "assets"
        for fam in load_yaml(fdir / "catalog.yaml").get("families", []):
            fid = fam["id"]
            if want_ids and fid not in want_ids:
                continue
            out_png = assets / f"{fid}-specimen.png"
            if out_png.is_file() and not args.force:
                skipped += 1
                continue
            if pick_file(fam) is None:
                print(f"  · {fdir.name}/{fid}: no font to render (premium) — supply a specimen image")
                skipped += 1
                continue
            try:
                font = resolve_font(fam, fdir.name, assets, args.refresh)
                if font is None:
                    failed += 1
                    continue
                sample = fam.get("specimenText") or DEFAULT_SAMPLE
                render(font, out_png, sample)
                print(f"  + {fdir.name}/{fid} → {out_png.relative_to(ROOT)}")
                rendered += 1
            except (requests.RequestException, zipfile.BadZipFile, subprocess.CalledProcessError) as e:
                print(f"  warn: {fdir.name}/{fid}: {e}", file=sys.stderr)
                failed += 1

    print(f"specimens: {rendered} rendered, {skipped} skipped, {failed} failed. "
          f"Review the PNGs, then run build_manifest.py + commit.")
    if failed:
        sys.exit(1)


if __name__ == "__main__":
    main()
