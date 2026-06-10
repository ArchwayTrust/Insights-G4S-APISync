# G4S API Sync — Microsoft Fabric notebooks

A re-platform of the `G4SApiSync` .NET console app as Fabric notebooks writing OneLake delta
tables. The data output is identical to the SQL Server version, with one deliberate change:
**all table and column names are mechanical snake_case** (`g4s.GroupTeachers` →
`g4s.group_teachers`, `StudentId` → `student_id`).

```
Go4Schools API ──> NB_G4S_Raw_Ingest ──> RAW lakehouse (g4s schema)
                                          • one delta table per endpoint (this run's pull only)
                                          • g4s.sync_results  (append-only run log)
                                          • g4s.sync_scope    (what this run pulled, drives the merge)
                                                  │
                                                  v
                              NB_G4S_Base_Merge ──> BASE lakehouse (g4s schema)
                                          • persists ALL academic years, never fully rebuilt
                                          • scope-driven delete + insert (replicates the .NET
                                            delete-then-bulk-insert incl. EF cascade deletes)
                                          • v_students / v_behaviour / v_session_attendance
                                            (materialised versions of the old SQL views)

on-prem SQL Server ──(pipeline Copy via gateway)──> RAW lakehouse ──> NB_G4S_Migrate_SQL_History
                                                                       (one-off history load into BASE)
```

## Prerequisites

- A Fabric workspace with the **raw** and **base** lakehouses (schema-enabled or legacy —
  both are supported via `SCHEMA_ENABLED`).
- An Azure **Key Vault** holding one secret per academy containing its G4S API key. The
  identity running the notebooks needs *get* permission on secrets
  (`notebookutils.credentials.getSecret` is used).
- The `VL_CORE` **variable library** in the workspace (already used by your other loads):

| variable | example | used for |
|---|---|---|
| `SCHEMA_ENABLED` | `true` | table naming: `…lakehouse.g4s.students` vs `…lakehouse.dbo.g4s_students` |
| `KEY_VAULT` | `https://kv-archway-core.vault.azure.net/` | API key secret resolution |
| `STORE_WORKSPACE_NAME` / `STORE_WORKSPACE_ID` | `WS_Insights` | fully-qualified table names |
| `RAW_LH_NAME` / `RAW_LH_ID` | `LH_Raw` | raw lakehouse |
| `BASE_LH_NAME` / `BASE_LH_ID` | `LH_Base` | base lakehouse |

Import the three `.Notebook` folders in this directory into the workspace (git sync or
upload). The notebooks deliberately pin **no default lakehouse** — everything is addressed
through the variable library. If your tenant requires a default lakehouse for Spark SQL,
attach the raw lakehouse; addressing still comes from `VL_CORE`.

## Academy configuration (replaces `sec.AcademySecurity`)

Edit the `ACADEMIES_JSON` cell near the top of **NB_G4S_Raw_Ingest**. One object per
academy; field meanings match the old SQL columns exactly:

```json
{
  "academy_code": "BAA",              // unique acronym (AcademyCode)
  "name": "Bluecoat Aspley Academy",  // informational
  "current_academic_year": "2026",    // "2026" = 2025/26 (CurrentAcademicYear)
  "api_key_secret": "g4s-apikey-baa", // Key Vault SECRET NAME — never the key itself
  "active": true,
  "lowest_year": 7,                   // attainment year-group range; 0 = Reception
  "highest_year": 13,
  "get_lesson_attendance": true,      // default window: yesterday only
  "get_session_attendance": true,     // default window: last 7 days .. today
  "attendance_from": null,            // optional ISO dates bounding both attendance windows
  "attendance_to": null,
  "get_behaviour": true,              // default window: last 14 days .. today
  "behaviour_from": null,
  "behaviour_to": null
}
```

Notes:

- **No API keys live in the notebook or in git** — only Key Vault secret names. Suggested
  secret naming: `g4s-apikey-<academy_code>`.
- **Historic years**: set `current_academic_year` to a prior year and run FULL once — the
  base layer keeps every year side by side (`data_set` column), exactly like the SQL app.
- The academy **list order matters** only for the shared staff endpoint: where two academies
  return the same staff id, the later academy wins (matching the .NET behaviour).

## Running and scheduling

`NB_G4S_Raw_Ingest` takes `sync_mode`, mirroring the old `.exe` arguments:

| sync_mode | old invocation | endpoints |
|---|---|---|
| `FULL` | no argument | everything: students → teaching → assessment → attainment → attendance → timetables → behaviour → users |
| `ATT` | `G4SApiSync.exe ATT` | session summaries, attendance codes, lesson marks, session marks |
| `BEH` | `G4SApiSync.exe BEH` | ATT set + behaviour classifications, event types, events |

Always run **NB_G4S_Base_Merge straight after the ingest** (it consumes raw
`g4s.sync_scope`). Suggested pipelines, each two chained notebook activities
(ingest → on-success → merge):

- `PL_G4S_FULL` — nightly, `sync_mode = "FULL"`.
- `PL_G4S_ATT` / `PL_G4S_BEH` — intra-day if wanted, `sync_mode = "ATT"` / `"BEH"`.

Do not overlap runs: the merge reads whatever the last ingest left in raw.

## One-off history migration

1. Build a pipeline **Copy activity** per `g4s.*` SQL table (34 tables: the 33 data tables
   plus `SyncResults`; skip `GradeTypes` and `sec.AcademySecurity`) from the on-prem SQL
   Server **through the on-premises data gateway** into the **raw** lakehouse, keeping the
   PascalCase table names with no transformation. Land them as `migration.<TableName>`
   (schema-enabled) or `dbo.<prefix><TableName>` (legacy — set `source_prefix`).
2. Run **NB_G4S_Migrate_SQL_History**. It renames columns to snake_case, casts types, and
   merges into base **idempotently** (keyed tables delete-by-natural-key then append; the
   identity tables `AttributeValues`/`ExamResults` are overwritten from the SQL snapshot).
   Safe to re-run.
3. Check the verification cell output: per-(academy, data_set) row counts source vs base
   must match.
4. Enable the scheduled pipelines, parallel-run against the old Task Scheduler job for a
   few days (parity queries below), then decommission the `.exe` job.

## Verifying parity with the SQL database

Per table, compare grouped counts (identity columns excluded — their values were load
artifacts in SQL too):

```sql
-- SQL Server                                   -- Fabric (SQL endpoint / Spark SQL)
SELECT Academy, DataSet, COUNT(*)               SELECT academy, data_set, COUNT(*)
FROM g4s.Students                               FROM <base>.g4s.students
GROUP BY Academy, DataSet;                      GROUP BY academy, data_set;
```

- Date-scoped tables (`student_session_marks`, `student_lesson_marks`, `beh_events`):
  compare over the window the new sync has pulled.
- `staff`: compare the set of `staff_id`s.
- `v_students`: spot-check the pivoted columns (`fsm`, `pp`, `sen_code`, `ks2_band`) for a
  sample of students against `g4s.v_Students`.
- After any run: `SELECT * FROM <raw>.g4s.sync_results WHERE run_id = '<run>' AND result = false`
  should return nothing.

## Operations

- **Run log**: raw `g4s.sync_results` — one row per endpoint call per academy (and per
  date / year group where the endpoint loops), with exception text on failure. Failures
  never abort a run, and the merge only touches scopes that succeeded, so a failed
  endpoint simply leaves the previous data in base (same retry-on-next-schedule model as
  the .NET app).
- **Re-runs are idempotent**: re-running the merge against the same raw pull converges to
  the same base state.
- **Offline testing**: `NB_G4S_Raw_Ingest` accepts `mock_dir` (a folder of
  `<endpoint_name>.json` fixture files) and `run_date` (pins "today" for the relative date
  windows) so the whole flow can be exercised without touching the live API.
- **Housekeeping**: schedule `OPTIMIZE`/`VACUUM` on the busiest base tables
  (`student_session_marks`, `attribute_values`, `markslot_marks`) as per your standard
  lakehouse maintenance.
- **Adding an endpoint** (the old four-step pattern, now three): add a flatten function +
  registry entry in `NB_G4S_Raw_Ingest`, a schema in both notebooks' schema dicts, and a
  `MERGE_SPEC` row in `NB_G4S_Base_Merge`.

## Known divergences from the .NET app (all deliberate)

1. **Year-group loop failures**: the .NET app stopped the remaining year groups for that
   academy after one failure; the notebooks log the failure and continue with the rest.
2. **Partial-failure handling**: the .NET app could leave a child table empty when the
   parent endpoint succeeded but the child pull failed (cascade delete, failed insert), and
   child inserts after a failed parent died on PK violations. The notebooks delete only
   successfully pulled scopes and skip child inserts whose parent scope failed —
   stale-but-consistent data is kept instead.
3. `v_students.nc_year` uses `TRY_CAST` (Spark) where the SQL view's `CONVERT(int, …)`
   would raise on unexpected values, and the "latest attribute value" pivot adds a
   deterministic tie-breaker where SQL's `TOP 1` was arbitrary on ties.
4. View columns containing spaces (`[KS2 Band]`, `[Student First Name]`, …) become
   snake_case (`ks2_band`, `student_first_name`, …).
5. Two .NET bugs are **preserved** for parity and marked with comments for a post-parity
   fix: `attendance_codes.protect_bm` is populated from the *school manager* flag, and a
   null mark id produces `session_mark_id`/`lesson_mark_id` of `"<academy><year>-"` rather
   than NULL.
