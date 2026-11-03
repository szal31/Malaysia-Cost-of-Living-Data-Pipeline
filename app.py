"""Malaysia's cost of living, kept up to date by the daily pipeline (run.py on GitHub Actions).

The page only reads what the pipeline published: data/marts/*.parquet and data/status.json.

Usage:  streamlit run app.py
"""
import json
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import streamlit as st

ROOT = Path(__file__).parent
DATA = Path(os.environ.get("PIPELINE_DATA", ROOT / "data"))  # tests point this at fixtures
REPO = "https://github.com/szal31/Malaysia-Cost-of-Living-Data-Pipeline"
NAMES = {"fuel": "Fuel prices", "fx": "Exchange rates", "cpi": "Inflation (CPI)"}
COLOURS = {"ok": "green", "late": "orange", "failed": "red"}
MYT = timezone(timedelta(hours=8))

st.set_page_config(page_title="Malaysia Cost of Living", page_icon=":material/local_gas_station:")


@st.cache_data(ttl=600)
def mart(name):
    return pd.read_parquet(DATA / "marts" / f"{name}.parquet")


@st.cache_data(ttl=600)
def status():
    path = DATA / "status.json"
    return json.loads(path.read_text()) if path.exists() else None


def day(d):
    return f"{d.day} {d:%b %Y}"


st.caption(":material/autorenew: Collected, checked and published every day by an automated pipeline")
st.title("Malaysia cost of living")
st.markdown("Fuel prices, the ringgit and inflation, kept up to date automatically from official open data.")

run = status()
if run:
    at = datetime.strptime(run["run_at"], "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc).astimezone(MYT)
    st.caption(f"Last pipeline run: {day(at)}, {at:%H:%M} Malaysia time · [Run history ↗]({REPO}/actions)")
    behind = [NAMES[s] for s, r in run["sources"].items() if r["status"] != "ok"]
    if behind:
        st.warning(f"{', '.join(behind)} didn't update in the last run, so the latest available numbers are shown. "
                   "See Pipeline health below.", icon=":material/warning:")
else:
    st.caption("Pipeline status unknown: no run has been recorded yet.")

fuel, fx, cpi = mart("fuel_prices"), mart("fx_rates"), mart("cpi")
national = cpi[(cpi.state == "Malaysia") & (cpi.division_code == "overall")].sort_values("date")
usd = fx[fx.currency == "USD"].sort_values("date")
f_now, f_prev = fuel.iloc[-1], fuel.iloc[-2]
u_now, u_prev = usd.iloc[-1], usd.iloc[-2]
c_now, c_prev = national.iloc[-1], national.iloc[-2]

c1, c2, c3 = st.columns(3)
budi = f_now.get("ron95_budi95")
c1.metric(f"RON95 market price · {day(f_now.date)}", f"RM{f_now.ron95:.2f}/litre",
          f"{f_now.ron95 - f_prev.ron95:+.2f} on last week", delta_color="inverse",
          help="The unsubsidised pump price, set weekly.")
if pd.notna(budi):  # since 2025 most Malaysians pay the targeted price, so show it beside the market one
    c1.caption(f"Eligible Malaysians pay **RM{budi:.2f}/litre** under BUDI95.")
c2.metric(f"Ringgit per US dollar · {day(u_now.date)}", f"RM{u_now.middle:.4f}",
          f"{u_now.middle - u_prev.middle:+.4f} on previous day", delta_color="inverse",
          help="Bank Negara's 17:00 closing rate, midpoint of buying and selling. Lower means a stronger ringgit.")
c3.metric(f"Inflation · {c_now.date:%b %Y}", f"{c_now.inflation_yoy:.1f}%",
          f"{c_now.inflation_yoy - c_prev.inflation_yoy:+.1f} pts on previous month", delta_color="inverse",
          help="Year-on-year change in Malaysia's consumer price index.")

tab_fuel, tab_fx, tab_cpi = st.tabs(["Fuel", "Ringgit", "Inflation"])
with tab_fuel:
    st.markdown("**Pump prices, RM per litre** (Peninsular Malaysia)")
    st.line_chart(fuel.set_index("date")[["ron95", "ron95_budi95", "ron97", "diesel"]].rename(
        columns={"ron95": "RON95 (market)", "ron95_budi95": "RON95 (BUDI95, targeted)", "ron97": "RON97",
                 "diesel": "Diesel"}), y_label="RM per litre")
    st.caption("Prices were frozen in 2018 and set weekly from 2019. Diesel rose 56% in June 2024 when its "
               "subsidy was targeted; RON95 moved to targeted pricing (BUDI95) in 2025.")
with tab_fx:
    options = sorted(fx.currency.unique())
    picked = st.multiselect("Currencies", options, default=[c for c in ("USD", "SGD") if c in options])
    if picked:
        st.markdown("**Ringgit per one unit of each currency**")
        st.line_chart(fx[fx.currency.isin(picked)].pivot(index="date", columns="currency", values="middle"),
                      y_label="RM")
with tab_cpi:
    latest = mart("cpi_latest")
    states = latest[latest.state != "Malaysia"].sort_values("inflation_yoy", ascending=False)
    st.markdown(f"**Inflation by state, {latest.date.max():%B %Y}** (year on year, %)")
    st.bar_chart(states, x="state", y="inflation_yoy", horizontal=True, sort="-inflation_yoy", x_label="%", y_label="")
    st.markdown("**National inflation since 2010** (year on year, %)")
    st.line_chart(national.set_index("date")["inflation_yoy"], y_label="%")

st.subheader("Pipeline health")
st.markdown("Every day the pipeline downloads each source, runs data checks in dbt, and only publishes data "
            "that passes. A source that fails keeps its last good data and emails the owner.")
if run:
    for s, r in run["sources"].items():
        age = f"{r['age_days']} days old" if r["age_days"] is not None else "no data"
        st.markdown(f"**{NAMES[s]}** :{COLOURS[r['status']]}-badge[{r['status']}] · latest {r['latest']} · "
                    f"{age} (limit {r['limit_days']}) · {r['rows']:,} rows")
        if r["detail"]:
            st.caption(r["detail"])
else:
    st.caption("Pipeline status unknown.")

st.caption("Sources: fuel prices from data.gov.my and CPI from OpenDOSM (CC BY 4.0); exchange rates: "
           f"Source: Bank Negara Malaysia. [How it works ↗]({REPO})")
