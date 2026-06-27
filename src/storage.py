"""Location-agnostic storage: same pipeline runs against local disk or S3.

`etl.py` / `train.py` never hardcode `data/...` or `s3://...`; they ask a
`Storage` for a path and read/write through it. Switching to S3 is then a flag,
not a code change — and at inference time you point at whatever base you want.

pandas reads/writes parquet & csv from `s3://` directly (needs `s3fs`). For json
and joblib artifacts we go through `fsspec`, which speaks both local and s3 with
one API.
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import fsspec
import joblib
import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_LOCAL_BASE = str(ROOT / "data")
DEFAULT_BUCKET = "svargas-turbofan-pm"

# medallion prefixes (bronze / silver / gold)
RAW = "raw"
PROCESSED = "processed"
PREDICTIONS = "predictions"


class Storage:
    """A base location ('/.../data' or 's3://bucket') with read/write helpers."""

    def __init__(self, base: str) -> None:
        self.base = base.rstrip("/")
        self.is_s3 = self.base.startswith("s3://")
        if not self.is_s3:
            # local: make sure the prefixes exist as real directories
            for sub in (RAW, PROCESSED, PREDICTIONS):
                Path(self.base, sub).mkdir(parents=True, exist_ok=True)

    # -- path building -------------------------------------------------
    def path(self, *parts: str) -> str:
        return "/".join([self.base, *parts])

    # -- tabular (pandas handles s3:// natively via s3fs) --------------
    def read_csv(self, rel: str, **kw) -> pd.DataFrame:
        return pd.read_csv(self.path(rel), **kw)

    def read_parquet(self, rel: str) -> pd.DataFrame:
        return pd.read_parquet(self.path(rel))

    def write_parquet(self, df: pd.DataFrame, rel: str) -> None:
        df.to_parquet(self.path(rel), index=False)

    # -- objects / json (via fsspec, works local + s3) -----------------
    def dump(self, obj, rel: str) -> None:
        with fsspec.open(self.path(rel), "wb") as fh:
            joblib.dump(obj, fh)

    def load(self, rel: str):
        with fsspec.open(self.path(rel), "rb") as fh:
            return joblib.load(fh)

    def write_json(self, obj, rel: str) -> None:
        with fsspec.open(self.path(rel), "w") as fh:
            json.dump(obj, fh, indent=2)

    def __repr__(self) -> str:
        return f"Storage(base={self.base!r}, s3={self.is_s3})"


def from_args(use_s3: bool, bucket: str | None = None) -> Storage:
    """Resolve a Storage from CLI flags / env.

    Precedence: explicit --bucket > TURBOFAN_S3_BUCKET env > DEFAULT_BUCKET.
    Without --s3, everything stays local under data/.
    """
    if use_s3:
        name = bucket or os.environ.get("TURBOFAN_S3_BUCKET", DEFAULT_BUCKET)
        return Storage(f"s3://{name}")
    return Storage(DEFAULT_LOCAL_BASE)
