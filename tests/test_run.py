import json
from datetime import date

import pandas as pd
import pytest

import ingest
import run

TODAY = date(2026, 11, 4)
FRESH = {"fuel": "2026-10-29", "fx": "2026-11-03", "cpi": "2026-09-01"}


@pytest.fixture
def data(tmp_path, monkeypatch):
    monkeypatch.setattr(run, "DATA", tmp_path)
    (tmp_path / "raw").mkdir()
    (tmp_path / "marts").mkdir()
    return tmp_path


def publish(data, source, day, text="A"):
    """What a successful ingest + dbt build leaves behind."""
    raw = data / "raw" / {"fuel": "fuel.csv", "cpi": "cpi.csv", "fx": "fx/2026-11.csv"}[source]
    raw.parent.mkdir(parents=True, exist_ok=True)
    raw.write_text(text)
    mart = data / "marts" / ("fx_rates/month=2026-11/data_0.parquet" if source == "fx" else f"{run.MART[source]}.parquet")
    mart.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({"date": pd.to_datetime([day])}).to_parquet(mart)


def fake(monkeypatch, data, fail=(), dbt_fail=(), days=FRESH):
    def ingest_(source, today):
        if source in fail:
            raise ingest.SourceError("0 rows")
        publish(data, source, days[source], text="B")
        return 10

    monkeypatch.setattr(run.ingest, "ingest", ingest_)
    monkeypatch.setattr(run, "dbt", lambda source: (source not in dbt_fail, "1 of 3 FAIL in_range"))


def status(data):
    return json.loads((data / "status.json").read_text())["sources"]


def test_failed_checks_restore_previous_files(data, monkeypatch):
    publish(data, "fuel", "2026-10-22", text="A")
    fake(monkeypatch, data, dbt_fail={"fuel"})
    assert run.main(TODAY) == 1
    assert (data / "raw" / "fuel.csv").read_text() == "A"
    s = status(data)["fuel"]
    assert s["status"] == "failed" and "FAIL" in s["detail"] and s["latest"] == "2026-10-22"


def test_one_source_failing_does_not_block_others(data, monkeypatch):
    fake(monkeypatch, data, fail={"fuel"})
    run.main(TODAY)
    s = status(data)
    assert s["fuel"]["status"] == "failed"
    assert s["fx"]["status"] == "ok" and s["cpi"]["status"] == "ok"


def test_late_source(data, monkeypatch):
    fake(monkeypatch, data, days={**FRESH, "cpi": "2026-07-01"})  # 126 days old, limit 100
    assert run.main(TODAY) == 1
    s = status(data)["cpi"]
    assert s["status"] == "late" and s["age_days"] == 126


def test_first_run_without_files(data, monkeypatch):
    fake(monkeypatch, data)
    assert run.main(TODAY) == 0
    assert all(v["status"] == "ok" for v in status(data).values())


def test_empty_download_fails_and_keeps_old_files(data, monkeypatch):
    publish(data, "fx", "2026-10-30", text="A")
    fake(monkeypatch, data, fail={"fx"})
    run.main(TODAY)
    assert (data / "raw" / "fx" / "2026-11.csv").read_text() == "A"
    assert status(data)["fx"]["status"] == "failed" and "0 rows" in status(data)["fx"]["detail"]


def test_status_records_run_time(data, monkeypatch):
    fake(monkeypatch, data)
    run.main(TODAY)
    assert json.loads((data / "status.json").read_text())["run_at"].endswith("Z")


def test_published_reads_partitioned_mart(data):
    publish(data, "fx", "2026-11-03")  # exchange rates are one Parquet file per month
    assert run._published("fx") == (date(2026, 11, 3), 1)


def test_cpi_85_days_old_is_ok(data, monkeypatch):
    # DOSM publishes month M about 50 days after the 1st of M, so the newest row is often 80+ days old
    fake(monkeypatch, data, days={**FRESH, "cpi": "2026-08-11"})
    assert run.main(TODAY) == 0
