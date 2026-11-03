# Malaysia Cost of Living Pipeline Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** A daily GitHub Actions job that collects Malaysian fuel prices, ringgit exchange rates and CPI, checks
them with dbt tests, publishes small Parquet tables and a status file, and a Streamlit page that shows them
with a pipeline health section.

**Architecture:** `ingest.py` downloads each source into `data/raw/`. `run.py` processes one source at a time:
it backs up that source's raw files, ingests, runs `dbt build` for that source's models (which also writes
the mart Parquet files), restores the backup if anything fails, then writes `data/status.json` with
per-source status and freshness. The workflow commits `data/`, then fails the job if any source wasn't ok,
so GitHub emails the owner. `app.py` reads only `data/marts/*.parquet` and `data/status.json`.

**Tech Stack:** Python 3.14, requests, pandas, pyarrow, duckdb, dbt-core 1.12 + dbt-duckdb 1.11, Streamlit
1.66, pytest, GitHub Actions.

**Spec:** `docs/superpowers/specs/2026-11-04-cost-of-living-pipeline-design.md`

## Global Constraints

- Free tools only; no secrets; all sources public. Python 3.14 locally (`py -3.14`; plain `python` is 3.15 and
  can't build pyyaml).
- Sources (verified 4 Nov 2026):
  - Fuel: `https://storage.data.gov.my/commodities/fuelprice.parquet`, keep `series_type == "level"`; columns
    `date, ron95, ron97, diesel, diesel_eastmsia, ron95_budi95, ron95_skps, diesel_skds, diesel_budi`. From 2017-03-30.
  - FX: `https://api.bnm.gov.my/public/exchange-rate` (latest, all currencies) and
    `.../exchange-rate/{CUR}/year/{y}/month/{m}` (history), header `Accept: application/vnd.BNM.API.v1+json`.
    From about 2020-12. `middle_rate` is null in history: store buying and selling, and derive the middle.
  - CPI: `https://storage.dosm.gov.my/cpi/{cpi_2d_state,cpi_2d_state_inflation,cpi_2d,cpi_2d_inflation}.parquet`,
    merged exactly as project 01's `prepare.py`: national rows get `state="Malaysia"`. Output columns
    `state,date,division_code,cpi_index,inflation_yoy,inflation_mom`.
- Freshness limits: fuel 10 days, FX 7 calendar days, CPI 75 days, measured from today to the latest date.
- Storage: FX raw is one CSV per month (`data/raw/fx/YYYY-MM.csv`); fuel `data/raw/fuel.csv`; CPI
  `data/raw/cpi.csv`. DuckDB file is not committed. Marts are Parquet in `data/marts/`.
- Every source is gated alone: a failure keeps its last good raw and mart files; the other sources still publish.
- `data/status.json` is written on every run.
- Commit only when `data/` changed (status.json changes every run by design).
- Credits: data.gov.my and OpenDOSM (CC BY 4.0); "Source: Bank Negara Malaysia" for rates.
- Page theme matches project 06 (`.streamlit/config.toml`: IBM Plex Sans, primary `#0369A1`, dark `#38BDF8`).
- Keep-alive URLs: https://rapidkl-ridership-analysis.streamlit.app/,
  https://malay-tweet-sentiment-analysis.streamlit.app/, https://malaysia-economic-ai-assistant.streamlit.app/

## Review Focus

1. **A source returns an empty or truncated file** (HTTP 200, few rows). Checks must catch it: a row-count floor
   per source, so the last good data stays and the status is failed (test in Task 3).
2. **A source changes its columns** (data.gov.my added the BUDI95 columns in 2025). A missing required column
   fails that source only; extra columns are ignored (test in Task 1).
3. **A BNM holiday or weekend**: the latest endpoint returns the previous working day's date. That is not a
   duplicate and not a failure (test in Task 1).
4. **The first run with empty `data/`**: backfill everything; no backup to restore (test in Task 3).
5. **The page when status.json says a source failed**: show the last good numbers, with the source marked
   failed and its latest date (test in Task 4).

---

### Task 1: Ingest the three sources

**Files:**
- Create: `ingest.py`, `requirements.txt`, `requirements-dev.txt`, `.gitignore` (exists, extend)
- Test: `tests/test_ingest.py`

**Interfaces:**
- Produces:
  - `RAW = ROOT/"data"/"raw"`; `class SourceError(Exception)` for a missing column, empty response or HTTP error.
  - `fetch_fuel() -> pd.DataFrame` (level rows, required columns `date, ron95, ron97, diesel`).
  - `fetch_cpi() -> pd.DataFrame` (project 01 columns).
  - `fetch_fx(months: list[str]) -> pd.DataFrame` with columns `currency, unit, date, buying, selling`, where
    months are `"YYYY-MM"`; plus `fx_latest() -> pd.DataFrame`, same columns.
  - `save_fuel(df)`, `save_cpi(df)`, `save_fx(df)`: FX merged into existing month files, dedup on
    `(currency, date)`, newest wins.
  - `ingest(source: str) -> int` for `"fuel" | "fx" | "cpi"`, returning rows saved. FX backfills from 2020-11
    when `data/raw/fx/` is empty; otherwise it refetches the current and previous month plus latest.

- [ ] **Step 1: Write failing tests** (no network: monkeypatch `requests.get` / `pd.read_parquet`)
  - `test_fuel_keeps_level_rows_only`: the fixture has level and change_weekly rows; only the level rows come back.
  - `test_fuel_missing_required_column_raises`: drop `ron95` and expect `SourceError`; an extra unknown column is fine.
  - `test_cpi_matches_project01_columns`: tiny fixtures for the 4 files. Columns equal project 01's list, the
    national rows have `state == "Malaysia"`, and there are no duplicate `(state, date, division_code)`.
  - `test_fx_parses_month_history`: a BNM JSON fixture with `middle_rate: null` gives rows with buying and selling.
  - `test_save_fx_splits_by_month_and_dedups`: save rows for 2026-10 and 2026-11, then save 2026-11 again with
    one changed rate. There are two files, no duplicates, and the new value wins.
  - `test_fx_weekend_latest_is_not_duplicate`: the latest endpoint returns Friday's date already saved; the
    rows stay the same and nothing is raised.
- [ ] **Step 2:** `.venv/Scripts/python -m pytest tests/test_ingest.py -q` → FAIL (no module `ingest`).
- [ ] **Step 3:** Implement `ingest.py`. Use timeouts of 60 s and turn `requests.RequestException` into
  `SourceError`. Pin package versions in `requirements.txt` (dbt-duckdb, duckdb, pandas, pyarrow, requests,
  streamlit) and put pytest in `requirements-dev.txt`.
- [ ] **Step 4:** Tests PASS. Then run the real thing once: `python -c "import ingest; [print(s, ingest.ingest(s)) for s in ('fuel','cpi','fx')]"`.
  Expected: fuel about 485 rows, CPI about 45k plus the national rows, and FX files from 2020-12 to 2026-11.
  Note how long the FX backfill took.
- [ ] **Step 5:** Commit the code and `data/raw/`.

### Task 2: dbt models and data checks

**Files:**
- Create: `dbt/dbt_project.yml`, `dbt/profiles.yml` (duckdb path `../warehouse.duckdb`; `external_root: ../data/marts`),
  `dbt/models/sources.yml`, `dbt/models/staging/stg_{fuel,fx,cpi}.sql`, `dbt/models/marts/{fuel_prices,fx_rates,cpi,cpi_latest}.sql`,
  `dbt/models/schema.yml`, `dbt/tests/generic/{in_range,max_gap_days,max_change_pct,min_rows}.sql`

**Interfaces:**
- Consumes: the raw files from Task 1, read in sources via `read_csv` (FX: glob `data/raw/fx/*.csv`).
- Produces: each model tagged with its source (`fuel`, `fx`, `cpi`), so `dbt build --select tag:fuel` runs one
  source. Marts materialized `external` (Parquet) at `data/marts/<model>.parquet`:
  - `fuel_prices(date, ron95, ron97, diesel, diesel_eastmsia, ron95_budi95, ...)`
  - `fx_rates(date, currency, buying, selling, middle)`, where `middle = (buying + selling) / 2`, per one unit
    of currency; BNM quotes some currencies per 100 units, so divide by `unit`.
  - `cpi` (project 01 columns) and `cpi_latest(state, inflation_yoy, date)` for the overall division in the latest month.
- Checks (dbt tests; values pinned here):
  - **fuel:**
    - `date` unique, not null;
    - `ron95` in 1.0–6.0, `ron97` in 1.0–8.0, `diesel` in 1.0–8.0;
    - `max_gap_days(date, 14)`;
    - `max_change_pct(ron95/diesel, 75)`, because diesel rose 56% in June 2024, which was real;
    - `min_rows(400)`.
  - **fx:**
    - `(currency, date)` unique;
    - `buying > 0`, `buying <= selling`;
    - USD middle in 3.0–6.0;
    - `max_change_pct(middle, 5)` per currency, day to day;
    - `min_rows(20000)`.
  - **cpi:**
    - `(state, date, division_code)` unique;
    - `cpi_index` in 50–300;
    - 17 distinct states;
    - every state has the same latest month;
    - `min_rows(40000)`.

- [ ] **Step 1:** Write the generic tests and `schema.yml` first. Run `dbt build` and expect errors (the models don't exist yet).
- [ ] **Step 2:** Write the sources, staging and marts.
- [ ] **Step 3:** `cd dbt && ../.venv/Scripts/dbt build --profiles-dir .` → all models and tests PASS on real
  data, and the 4 Parquet files exist in `data/marts/`.
- [ ] **Step 4:** Prove the checks bite: make a temporary copy of `fuel.csv` with one RON95 = 9.99, run
  `dbt build -s tag:fuel`, see the `in_range` test FAIL, then restore the file.
- [ ] **Step 5:** Commit `dbt/` and `data/marts/`.

### Task 3: Orchestrator, per-source gating and status

**Files:**
- Create: `run.py`
- Test: `tests/test_run.py`

**Interfaces:**
- Consumes: `ingest.ingest`, `ingest.SourceError`, and dbt via `subprocess` (`dbt build --select tag:<source>`).
- Produces:
  - `SOURCES = {"fuel": 10, "fx": 7, "cpi": 75}`, the freshness limits in days.
  - `run_source(name, today) -> dict`, returning `{status: "ok"|"late"|"failed", detail, rows, latest}`.
    It backs up the source's raw and mart files into a temp dir and restores them on any failure.
  - `main(today=None) -> int`, which writes `data/status.json` as `{"run_at": ISO8601 UTC, "sources": {...}}` and
    returns 0 only if every source is ok.
  - `latest` is read from the mart Parquet, so it reflects published data, not the attempt.

- [ ] **Step 1: Write failing tests**, with `ingest.ingest` and the dbt call monkeypatched:
  - `test_failed_checks_restore_previous_files`: start with raw fuel A, then have ingest write B and dbt fail.
    The file is A again, the status is `failed`, and `main()` returns 1.
  - `test_one_source_failing_does_not_block_others`: fuel fails, fx and cpi are ok; status.json shows that.
  - `test_late_source`: the CPI latest date is 80 days before `today`, so the status is `late` and the return is 1.
  - `test_first_run_without_files`: empty `data/`, the ingest works, and the status is ok (nothing to restore).
  - `test_empty_download_fails`: ingest raises `SourceError("0 rows")`, so the status is failed and the old files stay.
- [ ] **Step 2:** FAIL. **Step 3:** Implement. **Step 4:** PASS. Then run the real `python run.py`, which should exit 0 and write status.json with 3 ok sources.
- [ ] **Step 5:** Commit.

### Task 4: Streamlit page

**Files:**
- Create: `app.py`, `.streamlit/config.toml` (copied from project 06)
- Test: `tests/test_app.py` (AppTest with small fixture marts plus a status.json, via a `DATA` env var or
  monkeypatched path)

**Interfaces:**
- Consumes: the `data/marts/*.parquet` and `data/status.json` written by Tasks 2 and 3.
- Page:
  1. A title and one line on what it is, plus a "last updated" caption from `run_at`.
  2. Three headline `st.metric`s, each labelled with its date:
     - RON95 this week, with the change from last week (also show the BUDI95 price when present);
     - RM per USD, with the change from yesterday;
     - national inflation, latest month, with the change from the previous month.
  3. Tabs Fuel, Ringgit and Inflation, each with one chart:
     - Fuel: RON95, RON97 and diesel since 2017;
     - Ringgit: a currency multiselect defaulting to USD and SGD, and a line chart;
     - Inflation: a state bar chart for the latest month, plus a national line.
  4. A **Pipeline health** section: a table with source, status (ok/late/failed with a coloured badge), latest
     date, age in days, limit and rows, plus a link to the GitHub Actions runs. If any source isn't ok, show an
     `st.warning` above the headlines.
  5. A footer with credits.
- [ ] **Step 1:** Failing tests:
  - `test_headlines_show_dates`: the metric labels contain the fixture dates.
  - `test_failed_source_flagged`: the status has fuel failed, so a warning names fuel and the health table shows `failed`.
  - `test_missing_status_file`: no status.json, so the page still renders, with "status unknown".
- [ ] **Step 2–4:** FAIL → implement → PASS. Then run `streamlit run app.py` and check it in the browser at desktop and 375 px widths.
- [ ] **Step 5:** Commit.

### Task 5: Daily workflow and keep-alive

**Files:**
- Create: `.github/workflows/daily.yml`, `keepalive.py`
- Test: `tests/test_keepalive.py`

**Interfaces:**
- `keepalive.py`: `ping(url) -> tuple[int, bool]` returns the HTTP status and whether the page looks asleep
  (it contains "gone to sleep"). `main()` pings the 3 URLs, prints the results, and never fails the job.
- Workflow:
  - `on: schedule: cron "0 6 * * *"` (14:00 MYT) plus `workflow_dispatch`;
  - `permissions: contents: write`;
  - steps: checkout, setup-python 3.14 with pip cache, install `requirements.txt`, then
    `python run.py; echo "code=$?" >> $GITHUB_OUTPUT` (the step must not stop the job);
  - commit `data/` as `github-actions[bot]` only if `git status --porcelain data/` is non-empty, then push;
  - `python keepalive.py`, `continue-on-error: true`;
  - a final step that exits with the saved code, so GitHub emails the owner on failure.
- [ ] **Step 1:** Failing tests: `test_ping_detects_sleep_page` and `test_main_never_raises` (with `requests.get` raising).
- [ ] **Step 2–4:** FAIL → implement → PASS. Validate the YAML with `python -c "import yaml; yaml.safe_load(open(...))"`.
- [ ] **Step 5:** Commit.

### Task 6: README, publish, verify

**Files:**
- Create: `README.md` in the project 05/06 style:
  - a live link and a screenshot;
  - what it shows;
  - a flow diagram (Mermaid: sources → ingest → dbt checks → marts → Streamlit, with status → email);
  - the checks table;
  - how failures behave;
  - how to run it locally;
  - data and credits, including BNM API terms checked and noted.
- Steps:
  1. The owner creates the empty GitHub repo `Malaysia-Cost-of-Living-Data-Pipeline`; I push.
  2. Trigger the workflow by hand with `gh workflow run daily.yml` (if `gh` is authenticated; otherwise the
     owner clicks "Run workflow"). Check it goes green and that a bot commit appears only if data changed.
  3. The owner deploys `app.py` on Streamlit Community Cloud; I verify the live page.
  4. Check the keep-alive output in the run log. If plain requests don't wake or keep the apps awake, rule on
     a headless-browser fallback (Playwright) and note it.
  5. Run a whole-branch review with a fresh reviewer, the Review Focus above and the ledger rulings.
