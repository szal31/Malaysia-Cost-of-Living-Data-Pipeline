import pandas as pd
import pytest

import ingest


@pytest.fixture(autouse=True)
def raw_dir(tmp_path, monkeypatch):
    monkeypatch.setattr(ingest, "RAW", tmp_path)
    return tmp_path


def fuel_frame(**drop):
    df = pd.DataFrame({"series_type": ["level", "change_weekly", "level"],
                       "date": pd.to_datetime(["2026-10-22", "2026-10-29", "2026-10-29"]),
                       "ron95": [2.60, 0.1, 2.70], "ron97": [3.2, 0.1, 3.3], "diesel": [2.9, 0.2, 3.1],
                       "brand_new_column": [1, 2, 3]})
    return df.drop(columns=list(drop))


def test_fuel_keeps_level_rows_only(monkeypatch):
    monkeypatch.setattr(ingest.pd, "read_parquet", lambda url: fuel_frame())
    df = ingest.fetch_fuel()
    assert list(df.ron95) == [2.60, 2.70]
    assert "series_type" not in df


def test_fuel_missing_required_column_raises(monkeypatch):
    monkeypatch.setattr(ingest.pd, "read_parquet", lambda url: fuel_frame(ron95=True))
    with pytest.raises(ingest.SourceError):
        ingest.fetch_fuel()


def test_cpi_matches_project01_columns(monkeypatch):
    files = {
        "cpi_2d_state": pd.DataFrame({"state": ["Johor"], "date": ["2026-09-01"], "division": ["overall"],
                                      "index": [140.1]}),
        "cpi_2d_state_inflation": pd.DataFrame({"state": ["Johor"], "date": ["2026-09-01"], "division": ["overall"],
                                                "inflation_yoy": [1.9], "inflation_mom": [0.1]}),
        "cpi_2d": pd.DataFrame({"date": ["2026-09-01"], "division": ["overall"], "index": [135.0]}),
        "cpi_2d_inflation": pd.DataFrame({"date": ["2026-09-01"], "division": ["overall"],
                                          "inflation_yoy": [1.8], "inflation_mom": [0.0]}),
    }
    monkeypatch.setattr(ingest.pd, "read_parquet", lambda url: files[url.rsplit("/", 1)[1].split(".")[0]].copy())
    df = ingest.fetch_cpi()
    assert list(df.columns) == ["state", "date", "division_code", "cpi_index", "inflation_yoy", "inflation_mom"]
    assert set(df.state) == {"Johor", "Malaysia"}
    assert not df.duplicated(["state", "date", "division_code"]).any()


class Resp:
    def __init__(self, body, status=200):
        self.body, self.status_code = body, status

    def json(self):
        return self.body

    def raise_for_status(self):
        pass


def test_fx_parses_month_history(monkeypatch):
    body = {"data": {"currency_code": "JPY", "unit": 100, "rate": [
        {"date": "2026-10-01", "buying_rate": 2.5595, "selling_rate": 2.6045, "middle_rate": None}]}}
    monkeypatch.setattr(ingest, "CURRENCIES", ["JPY"])
    monkeypatch.setattr(ingest.HTTP, "get", lambda url, **kw: Resp(body))
    df = ingest.fetch_fx(["2026-10"])
    assert df.to_dict("records") == [{"currency": "JPY", "unit": 100, "date": "2026-10-01",
                                      "buying": 2.5595, "selling": 2.6045}]


def rows(currency, date, buying):
    return pd.DataFrame({"currency": [currency], "unit": [1], "date": [date], "buying": [buying],
                         "selling": [buying + 0.02]})


def test_save_fx_splits_by_month_and_dedups(raw_dir):
    ingest.save_fx(pd.concat([rows("USD", "2026-10-30", 4.20), rows("USD", "2026-11-03", 4.21)]))
    ingest.save_fx(rows("USD", "2026-11-03", 4.25))
    files = sorted(p.name for p in (raw_dir / "fx").iterdir())
    assert files == ["2026-10.csv", "2026-11.csv"]
    nov = pd.read_csv(raw_dir / "fx" / "2026-11.csv")
    assert len(nov) == 1 and nov.buying[0] == 4.25


def test_fx_weekend_latest_is_not_duplicate(raw_dir):
    ingest.save_fx(rows("USD", "2026-10-30", 4.20))
    ingest.save_fx(rows("USD", "2026-10-30", 4.20))  # Saturday's "latest" is still Friday
    assert len(pd.read_csv(raw_dir / "fx" / "2026-10.csv")) == 1


def test_http_error_becomes_source_error(monkeypatch):
    import requests

    def boom(url, **kw):
        raise requests.ConnectionError("down")
    monkeypatch.setattr(ingest.HTTP, "get", boom)
    with pytest.raises(ingest.SourceError):
        ingest.fx_latest()


def test_bnm_requests_retry_temporary_errors():
    retry = ingest.HTTP.get_adapter("https://api.bnm.gov.my").max_retries
    assert retry.total >= 3 and 503 in retry.status_forcelist and retry.backoff_factor > 0
