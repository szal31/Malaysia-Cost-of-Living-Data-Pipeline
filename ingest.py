"""Download Malaysia's fuel prices, ringgit exchange rates and CPI into data/raw/.

Fuel and CPI are small and replaced whole. Exchange rates are kept as one CSV per month, so a daily update
only rewrites the current month's file.

Usage:  python ingest.py [fuel|fx|cpi ...]
"""
import sys
from datetime import date
from pathlib import Path

import pandas as pd
import requests

ROOT = Path(__file__).parent
RAW = ROOT / "data" / "raw"
FUEL_URL = "https://storage.data.gov.my/commodities/fuelprice.parquet"
CPI_URL = "https://storage.dosm.gov.my/cpi/{}.parquet"
BNM = "https://api.bnm.gov.my/public/exchange-rate"
BNM_HEADERS = {"Accept": "application/vnd.BNM.API.v1+json"}
SESSION = {"session": "1700"}  # closing rate, all 27 currencies (the 11:30 session has only 7); history defaults differ, so pin it
FX_START = "2020-11"  # earliest month BNM's API returns
CURRENCIES = ["AED", "AUD", "BND", "CAD", "CHF", "CNY", "EGP", "EUR", "GBP", "HKD", "IDR", "INR", "JPY", "KHR",
              "KRW", "MMK", "NPR", "NZD", "PHP", "PKR", "SAR", "SDR", "SGD", "THB", "TWD", "USD", "VND"]
FUEL_COLUMNS = ["date", "ron95", "ron97", "diesel"]
CPI_COLUMNS = ["state", "date", "division_code", "cpi_index", "inflation_yoy", "inflation_mom"]


class SourceError(Exception):
    """A source couldn't be downloaded or doesn't look like it used to."""


def _parquet(url):
    try:
        return pd.read_parquet(url)
    except Exception as e:  # network errors surface from fsspec/urllib as many types
        raise SourceError(f"{url}: {e}") from e


def _require(df, columns, name):
    missing = set(columns) - set(df.columns)
    if missing:
        raise SourceError(f"{name} is missing columns {sorted(missing)}")
    if df.empty:
        raise SourceError(f"{name} returned 0 rows")


def fetch_fuel():
    df = _parquet(FUEL_URL)
    _require(df, ["series_type", *FUEL_COLUMNS], "fuel")
    df = df[df.series_type == "level"].drop(columns="series_type")
    df["date"] = pd.to_datetime(df.date).dt.strftime("%Y-%m-%d")
    return df.sort_values("date").reset_index(drop=True)


def fetch_cpi():
    """National and state CPI with inflation, merged as in project 01 (national rows are state "Malaysia")."""
    def load(index_file, infl_file, state=None):
        idx, infl = _parquet(CPI_URL.format(index_file)), _parquet(CPI_URL.format(infl_file))
        if state:
            idx, infl = idx.assign(state=state), infl.assign(state=state)
        _require(idx, ["state", "date", "division", "index"], index_file)
        _require(infl, ["state", "date", "division", "inflation_yoy", "inflation_mom"], infl_file)
        return idx.merge(infl, on=["state", "date", "division"], how="left")

    df = pd.concat([load("cpi_2d_state", "cpi_2d_state_inflation"), load("cpi_2d", "cpi_2d_inflation", "Malaysia")])
    df = df.rename(columns={"division": "division_code", "index": "cpi_index"})
    df["date"] = pd.to_datetime(df.date).dt.strftime("%Y-%m-%d")
    return df[CPI_COLUMNS].sort_values(["state", "division_code", "date"]).reset_index(drop=True)


def _bnm(path):
    try:
        r = requests.get(f"{BNM}{path}", headers=BNM_HEADERS, params=SESSION, timeout=60)
        if r.status_code == 404:  # BNM answers "No records found" this way
            return []
        r.raise_for_status()
        return r.json()["data"]
    except (requests.RequestException, ValueError, KeyError) as e:
        raise SourceError(f"BNM {path}: {e}") from e


def _fx_rows(entry, rates):
    return [{"currency": entry["currency_code"], "unit": entry["unit"], "date": r["date"],
             "buying": r["buying_rate"], "selling": r["selling_rate"]} for r in rates]


def fetch_fx(months):
    rows = []
    for cur in CURRENCIES:
        for m in months:
            y, mo = m.split("-")
            data = _bnm(f"/{cur}/year/{y}/month/{int(mo)}")
            if data:  # empty list for months before BNM's history starts
                rows += _fx_rows(data, data["rate"])
    return pd.DataFrame(rows, columns=["currency", "unit", "date", "buying", "selling"])


def fx_latest():
    rows = [r for e in _bnm("") for r in _fx_rows(e, [e["rate"]])]
    return pd.DataFrame(rows, columns=["currency", "unit", "date", "buying", "selling"])


def save_fuel(df):
    RAW.mkdir(parents=True, exist_ok=True)
    df.to_csv(RAW / "fuel.csv", index=False)


def save_cpi(df):
    RAW.mkdir(parents=True, exist_ok=True)
    df.to_csv(RAW / "cpi.csv", index=False)


def save_fx(df):
    folder = RAW / "fx"
    folder.mkdir(parents=True, exist_ok=True)
    df = df.dropna(subset=["buying", "selling"])
    for month, new in df.groupby(df.date.str[:7]):
        path = folder / f"{month}.csv"
        old = pd.read_csv(path) if path.exists() else new.iloc[:0]
        merged = pd.concat([old, new]).drop_duplicates(["currency", "date"], keep="last")
        merged.sort_values(["currency", "date"]).to_csv(path, index=False)


def months_between(start, end):
    return pd.period_range(start, end, freq="M").strftime("%Y-%m").tolist()


def ingest(source, today=None):
    """Download one source into data/raw/; returns rows fetched."""
    today = today or date.today()
    if source == "fuel":
        df = fetch_fuel()
        save_fuel(df)
    elif source == "cpi":
        df = fetch_cpi()
        save_cpi(df)
    elif source == "fx":
        backfill = not any((RAW / "fx").glob("*.csv"))
        this = today.strftime("%Y-%m")
        months = months_between(FX_START, this) if backfill else \
            months_between((pd.Period(this, "M") - 1).strftime("%Y-%m"), this)
        df = pd.concat([fetch_fx(months), fx_latest()])
        if df.empty:
            raise SourceError("fx returned 0 rows")
        save_fx(df)
    else:
        raise ValueError(source)
    return len(df)


if __name__ == "__main__":
    for s in sys.argv[1:] or ["fuel", "fx", "cpi"]:
        print(s, ingest(s), "rows")
