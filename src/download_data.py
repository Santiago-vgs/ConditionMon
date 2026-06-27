"""Download the NASA C-MAPSS turbofan dataset into data/raw/.

Source: NASA Open Data Portal (legacy Prognostics Data Repository mirror).
The archive contains all four subsets (FD001-FD004) plus the readme; by
default we only extract FD001, which is what Phase 1 of the build uses.

Usage:
    python src/download_data.py              # FD001 only (default)
    python src/download_data.py --all        # all subsets FD001-FD004
    python src/download_data.py --force      # re-download even if files exist

Stdlib only — no third-party packages needed to fetch the data.
"""

from __future__ import annotations

import argparse
import io
import ssl
import sys
import urllib.request
import zipfile
from pathlib import Path

try:
    import certifi

    SSL_CONTEXT = ssl.create_default_context(cafile=certifi.where())
except ImportError:
    # Fall back to the system default trust store.
    SSL_CONTEXT = ssl.create_default_context()

DATA_URL = "https://data.nasa.gov/docs/legacy/CMAPSSData.zip"
RAW_DIR = Path(__file__).resolve().parent.parent / "data" / "raw"

# The three files Phase 1 needs for the FD001 subset.
FD001_FILES = ["train_FD001.txt", "test_FD001.txt", "RUL_FD001.txt"]


def download_zip(url: str) -> bytes:
    """Fetch the zip into memory, following the NASA -> S3 redirect."""
    print(f"Downloading {url} ...")
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    with urllib.request.urlopen(req, timeout=120, context=SSL_CONTEXT) as resp:  # noqa: S310
        data = resp.read()
    print(f"  got {len(data) / 1024:.0f} KB")
    return data


def extract(zip_bytes: bytes, want_all: bool, force: bool) -> list[str]:
    """Extract the wanted .txt members from the zip into data/raw/."""
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    written: list[str] = []

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        for member in zf.namelist():
            name = Path(member).name
            if not name.endswith(".txt"):
                continue
            if not want_all and name not in FD001_FILES and name != "readme.txt":
                continue

            dest = RAW_DIR / name
            if dest.exists() and not force:
                print(f"  skip (exists): {name}")
                continue

            with zf.open(member) as src:
                dest.write_bytes(src.read())
            written.append(name)
            print(f"  wrote: {name}")

    return written


def verify() -> bool:
    """Confirm the three FD001 files landed and look sane."""
    ok = True
    for fname in FD001_FILES:
        path = RAW_DIR / fname
        if not path.exists():
            print(f"  MISSING: {fname}")
            ok = False
            continue
        with path.open() as fh:
            first = fh.readline().split()
        # train/test rows have 26 columns; RUL file has 1.
        cols = len(first)
        print(f"  {fname}: {path.stat().st_size / 1024:.0f} KB, {cols} cols in row 1")
    return ok


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--all", action="store_true", help="extract all subsets")
    parser.add_argument("--force", action="store_true", help="overwrite existing")
    args = parser.parse_args()

    zip_bytes = download_zip(DATA_URL)
    extract(zip_bytes, want_all=args.all, force=args.force)

    print("\nVerifying FD001 files:")
    if verify():
        print("\nDone. Data is in data/raw/")
        return 0
    print("\nVerification failed — check the output above.")
    return 1


if __name__ == "__main__":
    sys.exit(main())
