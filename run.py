"""The daily job: for each source, download, check with dbt, publish, and record how it went.

Each source is handled on its own. If its download or any of its checks fail, its previous files are put
back, so the page keeps showing the last good data, and the other sources still publish. data/status.json
is written every run; the exit code is 1 if any source isn't ok, which makes GitHub email the owner.

Usage:  python run.py
"""
import json
import shutil
import subprocess
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd

import ingest

ROOT = Path(__file__).parent
DATA = ROOT / "data"
SOURCES = {"fuel": 10, "fx": 7, "cpi": 75}  # how many days old the latest data may be
MART = {"fuel": "fuel_prices", "fx": "fx_rates", "cpi": "cpi"}
FILES = {"fuel": ["raw/fuel.csv", "marts/fuel_prices.parquet"],
         "fx": ["raw/fx", "marts/fx_rates.parquet"],
         "cpi": ["raw/cpi.csv", "marts/cpi.parquet", "marts/cpi_latest.parquet"]}
MYT = timezone(timedelta(hours=8))


def dbt(source):
    """Build and test one source's models; (passed, short report)."""
    dbt_exe = Path(sys.executable).with_name("dbt.exe" if sys.platform == "win32" else "dbt")
    r = subprocess.run([str(dbt_exe), "build", "--project-dir", "dbt", "--profiles-dir", "dbt",
                        "--select", f"tag:{source}", "--no-use-colors"], cwd=ROOT, capture_output=True, text=True)
    lines = [ln for ln in r.stdout.splitlines() if " FAIL " in ln or " ERROR " in ln]
    return r.returncode == 0, "\n".join(lines[-5:]) or r.stdout[-500:]


def _backup(source, folder):
    for rel in FILES[source]:
        src = DATA / rel
        if src.is_dir():
            shutil.copytree(src, folder / rel)
        elif src.exists():
            (folder / rel).parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(src, folder / rel)


def _restore(source, folder):
    for rel in FILES[source]:
        target, saved = DATA / rel, folder / rel
        if target.is_dir():
            shutil.rmtree(target)
        elif target.exists():
            target.unlink()
        if saved.is_dir():
            shutil.copytree(saved, target)
        elif saved.exists():
            shutil.copy2(saved, target)


def _published(source):
    path = DATA / "marts" / f"{MART[source]}.parquet"
    if not path.exists():
        return None, 0
    d = pd.read_parquet(path, columns=["date"])
    return pd.to_datetime(d.date).max().date(), len(d)


def run_source(source, today):
    with tempfile.TemporaryDirectory() as tmp:
        _backup(source, Path(tmp))
        try:
            ingest.ingest(source, today)
            passed, report = dbt(source)
            if not passed:
                raise ingest.SourceError(f"checks failed:\n{report}")
            status, detail = "ok", ""
        except Exception as e:  # any failure keeps the last good data; the email carries the detail
            _restore(source, Path(tmp))
            status, detail = "failed", f"{type(e).__name__}: {e}"[:600]
    latest, rows = _published(source)
    age = (today - latest).days if latest else None
    if status == "ok" and (age is None or age > SOURCES[source]):
        status, detail = "late", f"latest data is {age} days old (limit {SOURCES[source]})"
    return {"status": status, "detail": detail, "latest": str(latest) if latest else None,
            "age_days": age, "limit_days": SOURCES[source], "rows": rows}


def main(today=None):
    today = today or datetime.now(MYT).date()
    (DATA / "marts").mkdir(parents=True, exist_ok=True)
    results = {s: run_source(s, today) for s in SOURCES}
    run_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    (DATA / "status.json").write_text(json.dumps({"run_at": run_at, "sources": results}, indent=2) + "\n")
    for s, r in results.items():
        print(f"{s:5} {r['status']:6} latest {r['latest']} ({r['rows']} rows) {r['detail']}")
    return 0 if all(r["status"] == "ok" for r in results.values()) else 1


if __name__ == "__main__":
    sys.exit(main())
