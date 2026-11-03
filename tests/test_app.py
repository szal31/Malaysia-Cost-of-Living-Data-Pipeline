import json

import pandas as pd
import pytest
import streamlit as st
from streamlit.testing.v1 import AppTest


@pytest.fixture
def data(tmp_path, monkeypatch):
    st.cache_data.clear()
    marts = tmp_path / "marts"
    marts.mkdir()
    pd.DataFrame({"date": pd.to_datetime(["2026-10-22", "2026-10-29"]), "ron95": [2.60, 2.70],
                  "ron97": [3.20, 3.30], "diesel": [2.90, 3.10], "ron95_budi95": [1.99, 1.99]}
                 ).to_parquet(marts / "fuel_prices.parquet")
    pd.DataFrame({"date": pd.to_datetime(["2026-11-02", "2026-11-03"] * 2), "currency": ["USD", "USD", "SGD", "SGD"],
                  "buying": [4.20, 4.21, 3.20, 3.21], "selling": [4.22, 4.23, 3.22, 3.23],
                  "middle": [4.21, 4.22, 3.21, 3.22]}).to_parquet(marts / "fx_rates.parquet")
    pd.DataFrame({"state": ["Malaysia", "Malaysia", "Johor"], "date": pd.to_datetime(["2026-08-01", "2026-09-01"] * 1 + ["2026-09-01"]),
                  "division_code": ["overall"] * 3, "cpi_index": [134.0, 134.2, 140.1],
                  "inflation_yoy": [1.7, 1.8, 2.2], "inflation_mom": [0.1, 0.1, 0.2]}).to_parquet(marts / "cpi.parquet")
    pd.DataFrame({"state": ["Malaysia", "Johor"], "date": pd.to_datetime(["2026-09-01"] * 2),
                  "inflation_yoy": [1.8, 2.2], "inflation_mom": [0.1, 0.2]}).to_parquet(marts / "cpi_latest.parquet")
    monkeypatch.setenv("PIPELINE_DATA", str(tmp_path))
    return tmp_path


def write_status(data, fuel="ok"):
    src = {"status": "ok", "detail": "", "latest": "2026-11-03", "age_days": 1, "limit_days": 7, "rows": 4}
    (data / "status.json").write_text(json.dumps({"run_at": "2026-11-04T06:05:00Z", "sources": {
        "fuel": {**src, "status": fuel, "detail": "checks failed" if fuel != "ok" else ""},
        "fx": src, "cpi": src}}))


def app():
    at = AppTest.from_file("../app.py", default_timeout=30).run()
    assert not at.exception, at.exception
    return at


def test_headlines_show_dates(data):
    write_status(data)
    labels = " | ".join(m.label for m in app().metric)
    assert "29 Oct 2026" in labels and "market" in labels and "3 Nov 2026" in labels and "Sep 2026" in labels


def test_failed_source_flagged(data):
    write_status(data, fuel="failed")
    at = app()
    assert at.warning and "Fuel prices" in at.warning[0].value
    assert any("failed" in m.value for m in at.markdown)


def test_budi95_price_shown(data):
    write_status(data)
    assert any("RM1.99" in c.value for c in app().caption)


def test_missing_status_file(data):
    at = app()
    assert any("status unknown" in c.value.lower() for c in at.caption)
