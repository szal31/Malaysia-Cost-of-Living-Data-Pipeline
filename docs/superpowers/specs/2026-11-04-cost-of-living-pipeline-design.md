# Malaysia Cost of Living, Updated Automatically: Design

Portfolio project 07. Owner: a student applying for data analyst and junior data engineer internships in
Malaysia. Earlier projects: 01 Power BI inflation dashboard, 02 demand forecasting, 03 SQL RFM segmentation,
04 Rapid KL Streamlit app, 05 Malay sentiment model, 06 RAG chatbot over Bank Negara reports.

## Intent

None of the earlier projects run on their own: each was built once, by hand. This one is an automated data
pipeline. Every day it collects Malaysian price data by itself, checks it, models it in SQL and publishes
it to a web page. The page proves the pipeline works because its dates move forward without the owner
touching anything. It shows the skills recruiters ask about and the portfolio doesn't yet show: scheduling,
ingestion, data-quality testing, SQL modelling with dbt, and alerting.

## What it collects

All three sources were checked on 3–4 Nov 2026 and need no API key.

| Source | Where | Refresh | History available |
|---|---|---|---|
| Fuel prices: RON95, RON97, diesel (Peninsular and East Malaysia), and the targeted-subsidy prices (BUDI95, SKPS, SKDS, BUDI diesel) | data.gov.my, `https://storage.data.gov.my/commodities/fuelprice.parquet` (also the data-catalogue API, which redirects; follow redirects) | Weekly (Thursdays) | 30 Mar 2017 onwards. Rows are `series_type` = `level` (prices) or `change_weekly` (changes); keep `level`. |
| Ringgit exchange rates against the currencies BNM publishes (USD, SGD, CNY, EUR, GBP, JPY, THB, IDR and others) | Bank Negara open API, `https://api.bnm.gov.my/public/exchange-rate` with header `Accept: application/vnd.BNM.API.v1+json`; history via `/{currency}/year/{y}/month/{m}` | Every working day | About Dec 2020 onwards; earlier months return an empty list. `middle_rate` is null in history; use buying and selling rates. |
| Consumer price index by state and category, national and state, index and inflation | OpenDOSM, the same four files project 01's `prepare.py` uses: `cpi_2d_state`, `cpi_2d_state_inflation`, `cpi_2d`, `cpi_2d_inflation` (for example `https://storage.dosm.gov.my/cpi/cpi_2d_state.parquet`). National rows become `state = "Malaysia"`, as in project 01. | Monthly | Jan 2010 onwards (latest Sep 2026). |

Load the full history once, then only what is new.

## Goals

1. **Runs itself daily** on GitHub Actions (free), plus a manual "run now" button.
2. **Checks the data before publishing**: no missing or duplicate dates, prices in a sane range, no sudden
   impossible jumps, and each source fresh enough (fuel no older than about 10 days, rates about 5 working
   days, CPI about 75 days). A failed check stops publishing, so the page never shows bad data as current.
3. **SQL models in dbt over DuckDB**: raw → cleaned staging tables → small tables the page reads. dbt tests
   carry the data checks.
4. **Alerts on failure**: a failed run fails the GitHub Actions job, and GitHub emails the owner. No extra
   service.
5. **A Streamlit page** (owner's choice, on Streamlit Community Cloud) showing:
   - headline numbers: RON95 this week, ringgit per US dollar today, latest national inflation, each with its
     date and change;
   - trend charts for each source with sensible defaults (for example RON95 and diesel since 2017, MYR/USD and
     MYR/SGD since 2020, inflation by state);
   - a **pipeline health** section: when the last run happened, whether it passed, rows per source, and how
     fresh each source is. This is what makes it a data-engineering project rather than another dashboard.
6. **Keeps the owner's other Streamlit apps awake**: the daily job also visits projects 04, 05 and 06 so they
   don't go to sleep for lack of visitors.
   - 04: https://rapidkl-ridership-analysis.streamlit.app/
   - 05: https://malay-tweet-sentiment-analysis.streamlit.app/
   - 06: https://malaysia-economic-ai-assistant.streamlit.app/
   - Not yet verified that a plain HTTP request counts as activity; the builder checks, and uses a headless
     browser if it doesn't.
7. **A README in the style of projects 05 and 06**: what it shows first, then how it works, a diagram of the
   flow, how to run it, data sources and credits.

## Non-goals

- Forecasting or machine learning.
- Real-time or intraday data.
- Other datasets (weather was considered and dropped).
- Switching project 01 or 06 to read from this pipeline. This project only publishes a CPI table in the same
  columns as project 01's `data/fact_cpi.csv` at a stable URL in the repo, so that switch can be a later,
  separate change.
- Paid tools, cloud warehouses, or anything needing a credit card.

## Anti-goals (failure even if it technically works)

- The page showing stale data as if it were current. Every number shows its date, and the health section says
  plainly when a source is late.
- The git repo growing large from daily commits of whole data files.
- A pipeline that only works on the owner's laptop. Everything runs in GitHub Actions from a clean checkout.
- Hidden failures: a source that silently stops updating must turn the health section red and send an email.

## Constraints

- Free tools only. Development on a Windows laptop (Python 3.14 locally); GitHub Actions runs Linux.
- No secrets needed (all sources are public), so none in the repo.
- Credits: data.gov.my and OpenDOSM data are CC BY 4.0; credit "Source: Bank Negara Malaysia" for exchange rates.
  The builder checks BNM's API terms and notes them in the README.
- The bot's daily commit only happens when data actually changed.

## Calls made by the designer (owner can override)

- **Repo name** `Malaysia-Cost-of-Living-Data-Pipeline`, in `C:\Project\07-cost-of-living-pipeline`.
- **Storage:** raw data kept as files in the repo, split so a daily update touches small files (for example
  exchange rates in one file per month), not one growing file rewritten every day. The DuckDB database is
  rebuilt in each run, not committed. The small tables the page reads are committed as Parquet.
- **Schedule:** once a day, early afternoon Malaysia time, after BNM's noon rates are out.
- **Currencies on the page:** USD and SGD shown by default; all collected currencies stored.
- **Each source is checked and published on its own.** If fuel fails its checks, the last good fuel data stays
  on the page, marked late or failed in red, while fresh exchange rates and CPI still publish. The run still
  ends as failed so GitHub emails the owner. A late CPI release (common with DOSM) must not freeze the other
  two sources.
- **Run status is a small file committed on every run**, even when no data changed: run time, pass or fail
  per source, row counts and freshness. The health section reads only this file, so it works when nothing
  else changed (weekends, holidays, failed runs) and needs no live call to GitHub. This is the one exception
  to "commit only when data changed"; the file is tiny.

## Left to the builder

Folder layout, file formats for the stored data, exact check thresholds, chart choices, page layout and
styling (match project 06's theme), the keep-alive method, how the job commits, and test structure.
