# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# # NB_G4S_Raw_Ingest
#
# Pulls every Go4Schools ("G4S") API endpoint for each configured academy and writes the
# **current run's** data into the **raw** lakehouse `g4s` schema as delta tables. This is a
# 1:1 port of the `G4SApiSync` .NET console app — same endpoints, same row construction,
# same composite IDs — with tables/columns renamed to mechanical snake_case
# (`g4s.GroupTeachers` → `g4s.group_teachers`, `StudentId` → `student_id`).
#
# - Raw tables hold **only this run's pull** (overwritten each run). History lives in the
#   base lakehouse, maintained by `NB_G4S_Base_Merge` (run it straight after this one).
# - `g4s.sync_results` mirrors the .NET `SyncResults` log (append, one row per endpoint
#   call per academy/date/year-group).
# - `g4s.sync_scope` records exactly which scopes were pulled **successfully**, so the base
#   merge deletes precisely those scopes — even when the API returned zero rows.
# - Academy configuration lives in the `ACADEMIES_JSON` cell below (replaces the old
#   `sec.AcademySecurity` table). API keys are **Key Vault secret names**, never raw keys.
#
# **Parameters**
# | name | values | meaning |
# |---|---|---|
# | `sync_mode` | `FULL` / `ATT` / `BEH` | mirrors the .exe CLI arg: full sync / attendance only / attendance + behaviour |
# | `run_date` | `""` or ISO date | override "today" for the relative date windows (testing/backfill) |
# | `mock_dir` | `""` or a path | read `<endpoint>.json` fixture files instead of calling the API (offline testing) |
#
# See `Fabric/README.md` in the repo for setup (variable library, Key Vault, scheduling).

# PARAMETERS CELL ********************

sync_mode = "FULL"   # "FULL" | "ATT" | "BEH"
run_date = ""        # optional ISO date overriding today, e.g. "2026-06-10"
mock_dir = ""        # optional fixture directory for offline testing; empty = real API

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Environment: variable library, lakehouse addressing, run identity.

import datetime as dt
import json
import random
import time
import uuid
from zoneinfo import ZoneInfo

import requests
from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType, DateType, FloatType, IntegerType, LongType,
    StringType, StructField, StructType, TimestampType,
)

import notebookutils
from notebookutils import variableLibrary

# Get the entire variable library by name
vl = variableLibrary.getLibrary("VL_CORE")

# Fetch key environment variables
SCHEMA_ENABLED = vl.getVariable("SCHEMA_ENABLED")
KEY_VAULT = vl.getVariable("KEY_VAULT")
STORE_WORKSPACE_NAME = vl.getVariable("STORE_WORKSPACE_NAME")
STORE_WORKSPACE_ID = vl.getVariable("STORE_WORKSPACE_ID")
RAW_LH_NAME = vl.getVariable("RAW_LH_NAME")
RAW_LH_ID = vl.getVariable("RAW_LH_ID")
BASE_LH_NAME = vl.getVariable("BASE_LH_NAME")
BASE_LH_ID = vl.getVariable("BASE_LH_ID")


def qualify(lh_name: str, table: str) -> str:
    """Fully-qualified delta table name for both schema-enabled and legacy lakehouses."""
    if SCHEMA_ENABLED:
        return f"`{STORE_WORKSPACE_NAME}`.`{lh_name}`.`g4s`.`{table}`"
    return f"`{STORE_WORKSPACE_NAME}`.`{lh_name}`.`dbo`.`g4s_{table}`"


def raw_table(table: str) -> str:
    return qualify(RAW_LH_NAME, table)


BASE_URL = "https://api.go4schools.com"
RUN_ID = str(uuid.uuid4())
LONDON = ZoneInfo("Europe/London")

# The .NET app used the DB server's local clock (UK) for the relative date windows.
NOW = dt.datetime.now(LONDON).replace(tzinfo=None)
TODAY = dt.date.fromisoformat(run_date) if run_date else NOW.date()
MOCK_DIR = mock_dir.strip()

if sync_mode not in ("FULL", "ATT", "BEH"):
    raise ValueError(f"Unknown sync_mode '{sync_mode}' (expected FULL, ATT or BEH)")

if SCHEMA_ENABLED:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{STORE_WORKSPACE_NAME}`.`{RAW_LH_NAME}`.`g4s`")

print(f"SCHEMA_ENABLED is set to {SCHEMA_ENABLED} so setting up as follows:")
print(f"raw g4s tables: {raw_table('<table>')}")
print(f"sync_mode: {sync_mode} | run_id: {RUN_ID} | today: {TODAY}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# MARKDOWN ********************

# ## Academy configuration
#
# Replaces the old `sec.AcademySecurity` SQL table. One JSON object per academy:
#
# | field | meaning (same semantics as the SQL column it replaces) |
# |---|---|
# | `academy_code` | unique academy acronym, e.g. `"BAA"` (`AcademyCode`) |
# | `name` | full academy name (`Name`, informational) |
# | `current_academic_year` | dataset year, e.g. `"2026"` for 2025/26 (`CurrentAcademicYear`). Change it to pull a prior year — base keeps both. |
# | `api_key_secret` | **Key Vault secret name** holding the G4S API key (replaces the bare `APIKey`) |
# | `active` | only active academies are synced (`Active`) |
# | `lowest_year` / `highest_year` | NC year-group range for the attainment endpoints; `0` = Reception (`LowestYear`/`HighestYear`) |
# | `get_lesson_attendance` | pull per-lesson marks (`GetLessonAttendance`). Window: `attendance_from/to`, default **yesterday only** |
# | `get_session_attendance` | pull AM/PM session marks (`GetSessionAttendance`). Window: `attendance_from/to`, default **last 7 days to today** |
# | `attendance_from` / `attendance_to` | optional ISO dates bounding both attendance windows (`AttendanceFrom/To`); `null` = defaults above |
# | `get_behaviour` | pull behaviour classifications, event types and events (`GetBehaviour`). Window: `behaviour_from/to`, default **last 14 days to today** |
# | `behaviour_from` / `behaviour_to` | optional ISO dates (`BehaviourFrom/To`); `null` = default above |
#
# The list **order matters** for the shared staff endpoint: where two academies return the
# same staff id, the later academy in this list wins (matching the .NET run order).

# CELL ********************

ACADEMIES_JSON = """
[
  {
    "academy_code": "EXA",
    "name": "Example Academy",
    "current_academic_year": "2026",
    "api_key_secret": "g4s-apikey-exa",
    "active": false,
    "lowest_year": 7,
    "highest_year": 13,
    "get_lesson_attendance": true,
    "get_session_attendance": true,
    "attendance_from": null,
    "attendance_to": null,
    "get_behaviour": true,
    "behaviour_from": null,
    "behaviour_to": null
  }
]
"""

ACADEMIES = [a for a in json.loads(ACADEMIES_JSON) if a.get("active")]

_api_keys: dict = {}


def get_api_key(academy: dict) -> str:
    code = academy["academy_code"]
    if code not in _api_keys:
        _api_keys[code] = notebookutils.credentials.getSecret(KEY_VAULT, academy["api_key_secret"])
    return _api_keys[code]


print(f"Active academies: {[a['academy_code'] for a in ACADEMIES]}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Raw table schemas. Types mirror the SQL Server schema defined by the EF model:
# nvarchar -> string, int -> int, bit -> boolean, real -> float, Date -> date,
# datetime2 -> timestamp. attribute_values and exam_results carry no identity column in
# raw — the base merge generates attribute_value_id / exam_result_id (they were SQL
# IDENTITY columns whose values were load artifacts).

_TYPES = {
    "string": StringType(), "int": IntegerType(), "long": LongType(),
    "bool": BooleanType(), "float": FloatType(), "date": DateType(), "ts": TimestampType(),
}


def _schema(*fields) -> StructType:
    return StructType([StructField(n, _TYPES[t], True) for n, t in fields])


TABLE_SCHEMAS = {
    "students": _schema(
        ("student_id", "string"), ("g4s_stu_id", "int"), ("data_set", "string"), ("academy", "string"),
        ("date_of_birth", "date"), ("sex", "string"), ("legal_first_name", "string"),
        ("legal_last_name", "string"), ("preferred_first_name", "string"),
        ("preferred_last_name", "string"), ("middle_names", "string")),
    "education_details": _schema(
        ("student_id", "string"), ("g4s_stu_id", "int"), ("data_set", "string"), ("academy", "string"),
        ("upn", "string"), ("former_upn", "string"), ("nc_year", "string"),
        ("registration_group", "string"), ("house", "string"), ("admission_date", "date"),
        ("leaving_date", "date"), ("removed_from_source", "bool")),
    "student_attributes": _schema(
        ("student_attribute_id", "string"), ("student_id", "string"), ("g4s_stu_id", "int"),
        ("attribute_id", "int"), ("code", "string"), ("name", "string"), ("is_system", "bool")),
    "student_attribute_values": _schema(
        ("student_attribute_id", "string"), ("value", "string"), ("academic_year", "string"),
        ("date", "date")),
    "attribute_types": _schema(
        ("attribute_type_id", "string"), ("g4s_attribute_id", "int"), ("data_set", "string"),
        ("academy", "string"), ("attribute_group", "string"), ("code", "string"),
        ("attribute_name", "string"), ("is_system", "bool")),
    "attribute_values": _schema(
        ("attribute_type_id", "string"), ("student_id", "string"), ("value", "string"),
        ("academic_year", "string"), ("date", "date")),
    "departments": _schema(
        ("department_id", "string"), ("data_set", "string"), ("academy", "string"),
        ("g4s_department_id", "int"), ("name", "string")),
    "subjects": _schema(
        ("subject_id", "string"), ("g4s_subject_id", "int"), ("data_set", "string"),
        ("academy", "string"), ("name", "string"), ("code", "string"), ("year_group", "string"),
        ("department_id", "string"), ("qan", "string"), ("qualification_title", "string"),
        ("qualification_scheme_name", "string"), ("include_in_stats", "bool")),
    "groups": _schema(
        ("group_id", "string"), ("data_set", "string"), ("academy", "string"), ("name", "string"),
        ("code", "string"), ("subject_id", "string")),
    "group_students": _schema(("group_id", "string"), ("student_id", "string")),
    "group_teachers": _schema(("group_id", "string"), ("teacher_id", "string")),
    "teachers": _schema(
        ("teacher_id", "string"), ("g4s_teacher_id", "int"), ("data_set", "string"),
        ("academy", "string"), ("title", "string"), ("first_name", "string"), ("last_name", "string"),
        ("preferred_first_name", "string"), ("preferred_last_name", "string"),
        ("initials", "string"), ("code", "string")),
    "marksheets": _schema(
        ("marksheet_id", "string"), ("subject_id", "string"), ("data_set", "string"),
        ("academy", "string"), ("name", "string")),
    "marksheet_grades": _schema(
        ("student_id", "string"), ("marksheet_id", "string"), ("grade", "string"), ("alias", "string")),
    "markslots": _schema(
        ("markslot_id", "string"), ("marksheet_id", "string"), ("name", "string"), ("max_marks", "int")),
    "markslot_marks": _schema(
        ("student_id", "string"), ("markslot_id", "string"), ("grade", "string"), ("alias", "string"),
        ("mark", "float")),
    "prior_attainment": _schema(
        ("student_id", "string"), ("code", "string"), ("data_set", "string"), ("academy", "string"),
        ("name", "string"), ("value", "string"), ("value_academic_year", "string"),
        ("value_date", "date")),
    "grade_names": _schema(
        ("grade_name_id", "string"), ("grade_type_id", "int"), ("data_set", "string"),
        ("academy", "string"), ("nc_year", "int"), ("name", "string"), ("short_name", "string"),
        ("description", "string"), ("preferred_progress_grade", "bool"),
        ("preferred_target_grade", "bool")),
    "grades": _schema(
        ("student_id", "string"), ("grade_type_id", "int"), ("subject_id", "string"),
        ("data_set", "string"), ("academy", "string"), ("nc_year", "int"), ("name", "string"),
        ("alias", "string")),
    "exam_results": _schema(
        ("student_id", "string"), ("data_set", "string"), ("academy", "string"), ("nc_year", "int"),
        ("exam_academic_year", "string"), ("qan", "string"), ("qualification_title", "string"),
        ("exam_date", "date"), ("grade", "string"), ("ks123_literal", "string"),
        ("subject_id", "string")),
    "student_session_summaries": _schema(
        ("student_id", "string"), ("g4s_stu_id", "int"), ("data_set", "string"), ("academy", "string"),
        ("possible_sessions", "int"), ("present", "int"), ("approved_educational_activity", "int"),
        ("authorised_absence", "int"), ("unauthorised_absence", "int"),
        ("attendance_not_required", "int"), ("missing_mark", "int"), ("late", "int")),
    "attendance_codes": _schema(
        ("attendance_code_id", "string"), ("data_set", "string"), ("academy", "string"),
        ("code", "string"), ("attendance_label", "string"), ("attendance_officer_only", "bool"),
        ("protect_ao", "bool"), ("protect_sm", "bool"), ("protect_bm", "bool")),
    "attendance_alias_codes": _schema(
        ("attendance_alias_code_id", "string"), ("attendance_code_id", "string"),
        ("alias_code", "string"), ("label", "string")),
    "student_lesson_marks": _schema(
        ("student_id", "string"), ("date", "date"), ("class_id", "string"), ("data_set", "string"),
        ("academy", "string"), ("lesson_mark_id", "string"), ("lesson_alias_id", "string"),
        ("lesson_minutes_late", "int"), ("lesson_notes", "string")),
    "student_session_marks": _schema(
        ("student_id", "string"), ("date", "date"), ("session", "string"), ("data_set", "string"),
        ("academy", "string"), ("session_mark_id", "string"), ("session_alias_id", "string"),
        ("session_minutes_late", "int"), ("session_notes", "string")),
    "periods": _schema(
        ("period_id", "string"), ("data_set", "string"), ("academy", "string"),
        ("timetable_id", "string"), ("period_name", "string"), ("display_name", "string"),
        ("week_number", "int"), ("day_of_week", "string"), ("start", "date"), ("end", "date")),
    "tt_classes": _schema(
        ("class_id", "string"), ("data_set", "string"), ("academy", "string"),
        ("year_group", "string"), ("subject_code", "string"), ("group_code", "string"),
        ("period_id", "string")),
    "calendar": _schema(
        ("academy", "string"), ("data_set", "string"), ("date", "date"), ("timetable_id", "int"),
        ("week", "int"), ("day_type_code", "string")),
    "beh_classifications": _schema(
        ("beh_classification_id", "int"), ("data_set", "string"), ("academy", "string"),
        ("name", "string"), ("score", "int")),
    "beh_event_types": _schema(
        ("beh_event_type_id", "int"), ("data_set", "string"), ("academy", "string"),
        ("beh_classification_id", "int"), ("code", "string"), ("name", "string"),
        ("alias", "string"), ("significance", "string"), ("prioritise", "bool")),
    "beh_events": _schema(
        ("beh_event_id", "int"), ("data_set", "string"), ("academy", "string"),
        ("beh_event_type_id", "int"), ("event_date", "ts"), ("closed", "bool"),
        ("cancelled", "bool"), ("room_name", "string"), ("group_name", "string"),
        ("subject_code", "string"), ("year_group", "string"), ("home_notes", "string"),
        ("school_notes", "string"), ("created_time_stamp", "ts"), ("created_by_staff_id", "int"),
        ("modified_time_stamp", "ts"), ("modified_by_staff_id", "int")),
    "beh_event_students": _schema(
        ("beh_event_id", "int"), ("student_id", "string"), ("g4s_stu_id", "int")),
    # Internal raw-only table: ALL incoming behaviour event ids per pulled date, including
    # events skipped from insert because student_ids was null. The .NET id-collision delete
    # (GETBehEvents.cs) uses the full incoming id list, so the base merge needs it too.
    "beh_event_incoming_ids": _schema(
        ("academy", "string"), ("data_set", "string"), ("date", "date"), ("beh_event_id", "int")),
    "staff": _schema(
        ("staff_id", "int"), ("academy", "string"), ("email_address", "string"),
        ("first_name", "string"), ("last_name", "string"), ("display_name", "string"),
        ("title", "string")),
    "sync_results": _schema(
        ("sync_result_id", "long"), ("logged_at", "ts"), ("academy_code", "string"),
        ("end_point", "string"), ("data_set", "string"), ("year_group", "int"), ("result", "bool"),
        ("exception", "string"), ("inner_exception", "string"), ("run_id", "string"),
        ("sync_mode", "string")),
    "sync_scope": _schema(
        ("run_id", "string"), ("sync_mode", "string"), ("endpoint", "string"),
        ("academy", "string"), ("data_set", "string"), ("scope_type", "string"), ("date", "date"),
        ("year_group", "int"), ("attribute_group", "string"), ("pulled_at", "ts")),
}

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# HTTP client. Mirrors APIRequest.cs: Bearer auth, cursor pagination on has_more/cursor,
# per-page retries with exponential backoff + jitter on transient statuses, Retry-After
# honoured on 429 (capped), 600s timeout, and a 200ms pause after each completed pull.

TRANSIENT_STATUS = {408, 429, 500, 502, 503, 504}
MAX_RETRIES = 3            # attempts after the first try (4 total)
BASE_DELAY_S = 2.0         # exponential backoff base: ~2s, 4s, 8s (+ jitter)
MAX_RETRY_AFTER_S = 60     # cap on an honoured Retry-After header

SESSION = requests.Session()


class ApiCallError(Exception):
    pass


def _retry_delay_s(attempt: int, response) -> float:
    if response is not None and response.status_code == 429:
        retry_after = response.headers.get("Retry-After")
        if retry_after and retry_after.strip().isdigit() and int(retry_after) > 0:
            return min(int(retry_after), MAX_RETRY_AFTER_S)
    return BASE_DELAY_S * (2 ** (attempt - 1)) + random.uniform(0, 1)


def http_get_with_retry(url: str, headers: dict, params: dict):
    attempt = 0
    while True:
        attempt += 1
        try:
            response = SESSION.get(url, headers=headers, params=params, timeout=600)
        except (requests.exceptions.ConnectionError, requests.exceptions.Timeout):
            if attempt <= MAX_RETRIES:
                time.sleep(_retry_delay_s(attempt, None))
                continue
            raise
        if response.status_code == 200:
            return response
        if response.status_code in TRANSIENT_STATUS and attempt <= MAX_RETRIES:
            time.sleep(_retry_delay_s(attempt, response))
            continue
        raise ApiCallError(f"{response.status_code} - {response.reason}")


def api_get_all(api_key: str, path_template: str, envelope: str, academic_year: str,
                year_group: str = None, date: dt.date = None, mock_key: str = None) -> list:
    """Fetch every page of an endpoint and return the combined item list.

    Path placeholders ({academicYear}/{yearGroup}/{date}) are substituted; values without a
    placeholder are sent as query parameters (the staff endpoint takes academicYear that
    way). A bare-list response is returned as-is (no pagination), matching the .NET
    deserialisation fallback; a dict without the envelope key fails the scope, exactly as
    the .NET endpoint run failed.
    """
    if MOCK_DIR:
        return _load_mock(mock_key, envelope)

    path = path_template
    params = {}
    if "{academicYear}" in path:
        path = path.replace("{academicYear}", str(academic_year))
    else:
        params["academicYear"] = academic_year
    if year_group is not None:
        if "{yearGroup}" in path:
            path = path.replace("{yearGroup}", str(year_group))
        else:
            params["yearGroup"] = year_group
    if date is not None:
        date_str = date.strftime("%Y-%m-%d")
        if "{date}" in path:
            path = path.replace("{date}", date_str)
        else:
            params["date"] = date_str

    headers = {"Authorization": "Bearer " + api_key}
    items = []
    cursor = None
    while True:
        page_params = dict(params)
        if cursor is not None:
            page_params["cursor"] = cursor
        body = http_get_with_retry(BASE_URL + path, headers, page_params).json()
        if isinstance(body, list):
            items = body
            break
        if not isinstance(body, dict) or body.get(envelope) is None:
            raise ApiCallError(f"Response missing '{envelope}' envelope for {path}")
        items.extend(body[envelope])
        if body.get("has_more"):
            cursor = body.get("cursor")
        else:
            break
    time.sleep(0.2)
    return items


def _load_mock(mock_key: str, envelope: str) -> list:
    with open(f"{MOCK_DIR.rstrip('/')}/{mock_key}.json") as fh:
        body = json.load(fh)
    if isinstance(body, list):
        return body
    if body.get(envelope) is None:
        raise ApiCallError(f"Mock {mock_key} missing '{envelope}' envelope")
    return list(body[envelope])

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Parsing helpers. The .NET app used three distinct behaviours and they are preserved:
#  - parse_exact_date: DateTime.ParseExact("yyyy-MM-ddTHH:mm:ssZ") — raises on bad/missing
#    input (student date_of_birth fails the whole endpoint, as before).
#  - try_parse_date: DateTime.TryParseExact -> date or None.
#  - parse_iso_ts/parse_iso_date: Newtonsoft's automatic DateTime parsing (behaviour
#    timestamps, exam/calendar/period/mark dates) — tolerant ISO-8601.

TS_FORMAT = "%Y-%m-%dT%H:%M:%SZ"


def parse_exact_date(value: str) -> dt.date:
    return dt.datetime.strptime(value, TS_FORMAT).date()


def try_parse_date(value):
    if not isinstance(value, str):
        return None
    try:
        return dt.datetime.strptime(value, TS_FORMAT).date()
    except ValueError:
        return None


def parse_iso_ts(value):
    if value in (None, ""):
        return None
    return dt.datetime.fromisoformat(str(value).replace("Z", "+00:00")).replace(tzinfo=None)


def parse_iso_date(value):
    ts = parse_iso_ts(value)
    return ts.date() if ts else None


def cid(academy: str, ac_year: str, g4s_id) -> str:
    """Composite row id: AcademyCode + AcYear + '-' + id (AddMigrationReadme convention)."""
    return f"{academy}{ac_year}-{g4s_id}"


def opt_cid(academy: str, ac_year: str, g4s_id) -> str:
    # .NET quirk preserved: a null mark/alias id still produced "<Academy><Year>-" because
    # nullable int .ToString() returns "" (GETStudentSessionMarks/GETStudentLessonMarks).
    return f"{academy}{ac_year}-{'' if g4s_id is None else g4s_id}"

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Run logging and raw writes. sync_results mirrors the .NET SyncResults table; sync_scope
# is new — it records each successfully pulled scope so the base merge deletes exactly
# what this run covered (including scopes that legitimately returned zero rows).

_sync_results: list = []
_sync_scopes: list = []
_written_this_run: set = set()


def log_sync_result(academy_code, end_point, data_set, result,
                    year_group=None, exception=None, inner_exception=None):
    logged_at = dt.datetime.now(LONDON).replace(tzinfo=None)
    _sync_results.append({
        "logged_at": logged_at, "academy_code": academy_code, "end_point": end_point,
        "data_set": data_set, "year_group": year_group, "result": result,
        "exception": exception, "inner_exception": inner_exception,
        "run_id": RUN_ID, "sync_mode": sync_mode,
    })
    print(f"{logged_at} {academy_code} - {end_point} - {result}"
          + (f" - {exception}" if exception else ""))


def record_scope(endpoint, academy, data_set, scope_type,
                 date=None, year_group=None, attribute_group=None):
    _sync_scopes.append({
        "run_id": RUN_ID, "sync_mode": sync_mode, "endpoint": endpoint, "academy": academy,
        "data_set": data_set, "scope_type": scope_type, "date": date, "year_group": year_group,
        "attribute_group": attribute_group,
        "pulled_at": dt.datetime.now(LONDON).replace(tzinfo=None),
    })


def _to_df(table: str, rows: list):
    schema = TABLE_SCHEMAS[table]
    data = [tuple(row.get(field.name) for field in schema.fields) for row in rows]
    return spark.createDataFrame(data, schema)


def write_raw(table: str, rows: list):
    # First write of a table this run replaces last run's pull; subsequent writes append
    # (the four attribute endpoints share attribute_types/attribute_values).
    mode = "append" if table in _written_this_run else "overwrite"
    (_to_df(table, rows).write.mode(mode).option("overwriteSchema", "true")
        .format("delta").saveAsTable(raw_table(table)))
    _written_this_run.add(table)
    print(f"  raw {table}: {mode} {len(rows)} rows")


def clear_sync_scope():
    # Emptied up-front so a crashed run can never pair stale scopes with new raw data.
    _to_df("sync_scope", []).write.mode("overwrite").option("overwriteSchema", "true") \
        .format("delta").saveAsTable(raw_table("sync_scope"))


def flush_logs():
    try:
        max_id = spark.sql(
            f"SELECT COALESCE(MAX(sync_result_id), 0) FROM {raw_table('sync_results')}"
        ).first()[0]
    except Exception:
        max_id = 0
    rows = [dict(r, sync_result_id=max_id + i + 1) for i, r in enumerate(_sync_results)]
    _to_df("sync_results", rows).write.mode("append").format("delta") \
        .saveAsTable(raw_table("sync_results"))
    _to_df("sync_scope", _sync_scopes).write.mode("overwrite").format("delta") \
        .saveAsTable(raw_table("sync_scope"))
    print(f"sync_results: +{len(rows)} rows | sync_scope: {len(_sync_scopes)} scopes")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Flatteners — one per endpoint, each mirroring the DataTable construction in the matching
# GETxxx.cs class. Every function takes the deserialised item list plus the academy
# context and returns {table_name: [row_dicts]}.


def flatten_students(items, a, y, ctx):
    rows = []
    for it in items:
        rows.append({
            "student_id": cid(a, y, it["id"]), "data_set": y, "academy": a,
            "g4s_stu_id": it["id"],
            "legal_first_name": it.get("legal_first_name"),
            "legal_last_name": it.get("legal_last_name"),
            "preferred_first_name": it.get("preferred_first_name"),
            "preferred_last_name": it.get("preferred_last_name"),
            "middle_names": it.get("middle_names"), "sex": it.get("sex"),
            # Strict parse: a bad/missing date_of_birth fails the endpoint (ParseExact).
            "date_of_birth": parse_exact_date(it.get("date_of_birth")),
        })
    return {"students": rows}


def flatten_education_details(items, a, y, ctx):
    details, attribs, attrib_values = [], [], []
    for it in items:
        stu_id = cid(a, y, it["student_id"])
        if it.get("student_education_attributes") is not None:
            for att in it["student_education_attributes"]:
                att_id = f"{a}{y}-{it['student_id']}-{att['attribute_id']}"
                for val in att["attribute_values"]:
                    attrib_values.append({
                        "student_attribute_id": att_id, "value": val.get("value"),
                        "academic_year": val.get("academic_year"),
                        "date": try_parse_date(val.get("date")),
                    })
                attribs.append({
                    "student_attribute_id": att_id, "student_id": stu_id,
                    "g4s_stu_id": it["student_id"], "attribute_id": att["attribute_id"],
                    "code": att.get("code"), "name": att.get("name"),
                    "is_system": att.get("is_system", False),
                })
        details.append({
            "student_id": stu_id, "academy": a, "data_set": y, "g4s_stu_id": it["student_id"],
            "upn": it.get("upn"), "former_upn": it.get("former_upn"),
            "nc_year": it.get("national_curriculum_year"),
            "registration_group": it.get("registration_group"), "house": it.get("house"),
            "removed_from_source": it.get("deleted_from_source", False),
            "admission_date": try_parse_date(it.get("admission_date")),
            "leaving_date": try_parse_date(it.get("leaving_date")),
        })
    return {"education_details": details, "student_attributes": attribs,
            "student_attribute_values": attrib_values}


def make_flatten_attributes(group: str):
    # Shared by the General/Demographic/Send/Sensitive endpoints; only the group label and
    # URL differ (GETGeneralAttributes.cs et al).
    def flatten(items, a, y, ctx):
        types, values = [], []
        for it in items:
            type_id = f"{a}{y}-{group}-{it['id']}"
            if it.get("students_and_attribute_values") is not None:
                for val in it["students_and_attribute_values"]:
                    values.append({
                        "attribute_type_id": type_id,
                        "student_id": cid(a, y, val["student_id"]),
                        "value": val.get("value"), "academic_year": val.get("academic_year"),
                        "date": try_parse_date(val.get("date")),
                    })
            types.append({
                "attribute_type_id": type_id, "g4s_attribute_id": it["id"], "data_set": y,
                "academy": a, "attribute_group": group, "code": it.get("code"),
                "attribute_name": it.get("name"), "is_system": it.get("is_system", False),
            })
        return {"attribute_types": types, "attribute_values": values}
    return flatten


def flatten_departments(items, a, y, ctx):
    return {"departments": [{
        "department_id": cid(a, y, it["id"]), "data_set": y, "academy": a,
        "g4s_department_id": it["id"], "name": it.get("name"),
    } for it in items]}


def flatten_subjects(items, a, y, ctx):
    return {"subjects": [{
        "subject_id": cid(a, y, it["id"]), "data_set": y, "academy": a,
        "g4s_subject_id": it["id"], "name": it.get("name"), "code": it.get("code"),
        "year_group": it.get("year_group"),
        "department_id": cid(a, y, it.get("department_id", 0)),
        "qan": it.get("qan"), "qualification_title": it.get("qualification_title"),
        "qualification_scheme_name": it.get("qualification_scheme_name"),
        "include_in_stats": it.get("include_in_stats", False),
    } for it in items]}


def flatten_groups(items, a, y, ctx):
    return {"groups": [{
        "group_id": cid(a, y, it["id"]), "data_set": y, "academy": a, "name": it.get("name"),
        "code": it.get("code"), "subject_id": cid(a, y, it.get("subject_id", 0)),
    } for it in items]}


def flatten_group_students(items, a, y, ctx):
    rows = []
    for it in items:
        for stu in it["student_ids"]:
            rows.append({"group_id": cid(a, y, it["group_id"]), "student_id": cid(a, y, stu)})
    return {"group_students": rows}


def flatten_teachers(items, a, y, ctx):
    return {"teachers": [{
        "teacher_id": cid(a, y, it["id"]), "g4s_teacher_id": it["id"], "data_set": y,
        "academy": a, "title": it.get("title"), "first_name": it.get("first_name"),
        "last_name": it.get("last_name"),
        "preferred_first_name": it.get("preferred_first_name"),
        "preferred_last_name": it.get("preferred_last_name"),
        "initials": it.get("initials"), "code": it.get("code"),
    } for it in items]}


def flatten_group_teachers(items, a, y, ctx):
    rows = []
    for it in items:
        for tea in it["teacher_ids"]:
            rows.append({"group_id": cid(a, y, it["group_id"]), "teacher_id": cid(a, y, tea)})
    return {"group_teachers": rows}


def flatten_markbooks(items, a, y, ctx):
    marksheets, markslots = [], []
    for mb in items:
        for msh in mb["marksheets"]:
            msh_id = cid(a, y, msh["id"])
            for msl in msh["markslots"]:
                markslots.append({
                    "markslot_id": cid(a, y, msl["id"]), "marksheet_id": msh_id,
                    "name": msl.get("name"), "max_marks": msl.get("max", 0),
                })
            marksheets.append({
                "marksheet_id": msh_id, "subject_id": cid(a, y, mb["id"]),
                "data_set": y, "academy": a, "name": msh.get("name"),
            })
    return {"marksheets": marksheets, "markslots": markslots}


def flatten_marksheet_grades(items, a, y, ctx):
    rows = []
    for ms in items:
        for msg in ms["grades"]:
            rows.append({
                "marksheet_id": cid(a, y, ms["id"]), "student_id": cid(a, y, msg["student_id"]),
                "grade": msg.get("grade"), "alias": msg.get("alias"),
            })
    return {"marksheet_grades": rows}


def flatten_markslot_marks(items, a, y, ctx):
    rows = []
    for ms in items:
        for msm in ms["marks"]:
            mark = msm.get("mark")
            rows.append({
                "markslot_id": cid(a, y, ms["id"]), "student_id": cid(a, y, msm["student_id"]),
                "grade": msm.get("grade"), "alias": msm.get("alias"),
                "mark": float(mark) if mark is not None else None,
            })
    return {"markslot_marks": rows}


def flatten_prior_attainment(items, a, y, ctx):
    rows = []
    for typ in items:
        for val in typ["values"]:
            rows.append({
                "student_id": cid(a, y, val["student_id"]), "data_set": y, "academy": a,
                "name": typ.get("name"), "code": typ.get("code"), "value": val.get("value"),
                "value_academic_year": val.get("academic_year"),
                "value_date": try_parse_date(val.get("date")),
            })
    return {"prior_attainment": rows}


def flatten_grade_names(items, a, y, ctx):
    # grade_name_id uses the year-group STRING ("Reception" for 0); nc_year stores the int.
    return {"grade_names": [{
        "grade_name_id": f"{a}{y}-{ctx['year_group_str']}-{it['id']}",
        "grade_type_id": it["id"], "data_set": y, "academy": a,
        "nc_year": ctx["year_group_int"], "name": it.get("name"),
        "short_name": it.get("short_name"), "description": it.get("description"),
        "preferred_progress_grade": it.get("is_preferred_progress_grade", False),
        "preferred_target_grade": it.get("is_preferred_target_grade", False),
    } for it in items]}


def flatten_grades(items, a, y, ctx):
    # GradeTypeId 6 ("Actual") is excluded — those grades have no linked subject
    # (GETGrades.cs).
    return {"grades": [{
        "grade_type_id": it["grade_type_id"],
        "subject_id": cid(a, y, it["subject_id"]),
        "student_id": cid(a, y, it["student_id"]),
        "data_set": y, "academy": a, "nc_year": ctx["year_group_int"],
        "name": it.get("name"), "alias": it.get("alias"),
    } for it in items if it.get("grade_type_id") != 6]}


def flatten_exam_results(items, a, y, ctx):
    rows = []
    for it in items:
        subject_id = it.get("subject_id")
        rows.append({
            "student_id": cid(a, y, it.get("student_id", 0)), "data_set": y, "academy": a,
            "nc_year": ctx["year_group_int"], "exam_academic_year": it.get("exam_academic_year"),
            "qan": it.get("qan"), "qualification_title": it.get("qualification_title"),
            "grade": it.get("grade"), "ks123_literal": it.get("ks123literal"),
            "subject_id": cid(a, y, subject_id) if subject_id is not None else None,
            "exam_date": parse_iso_date(it.get("exam_date")),
        })
    return {"exam_results": rows}


def flatten_session_summaries(items, a, y, ctx):
    return {"student_session_summaries": [{
        "student_id": cid(a, y, it["student_id"]), "g4s_stu_id": it["student_id"],
        "data_set": y, "academy": a,
        "possible_sessions": it.get("possible_sessions", 0), "present": it.get("present", 0),
        "approved_educational_activity": it.get("approved_educational_activity", 0),
        "authorised_absence": it.get("authorised_absence", 0),
        "unauthorised_absence": it.get("unauthorised_absence", 0),
        "attendance_not_required": it.get("attendance_not_required", 0),
        "missing_mark": it.get("missing_mark", 0), "late": it.get("late", 0),
    } for it in items]}


def flatten_attendance_codes(items, a, y, ctx):
    codes, aliases = [], []
    for it in items:
        code_id = cid(a, y, it["id"])
        for al in it["aliases"]:
            aliases.append({
                "attendance_alias_code_id": cid(a, y, al["alias_id"]),
                "attendance_code_id": code_id,
                "alias_code": al.get("alias_code"), "label": al.get("alias_label"),
            })
        codes.append({
            "attendance_code_id": code_id, "data_set": y, "academy": a,
            "code": it.get("code"), "attendance_label": it.get("label"),
            "attendance_officer_only": it.get("attendance_officer_only", False),
            "protect_ao": it.get("protect_if_entered_by_attendance_officer", False),
            "protect_sm": it.get("protect_if_entered_by_school_manager", False),
            # .NET bug preserved for parity: ProtectBM was populated from the SM flag
            # (GETAttendanceCodes.cs); switch to protect_if_entered_by_behaviour_manager
            # once parity sign-off is done.
            "protect_bm": it.get("protect_if_entered_by_school_manager", False),
        })
    return {"attendance_codes": codes, "attendance_alias_codes": aliases}


def flatten_lesson_marks(items, a, y, ctx):
    rows = []
    for it in items:
        alias_id = it.get("lesson_alias_id")
        rows.append({
            "data_set": y, "academy": a, "student_id": cid(a, y, it["student_id"]),
            "date": parse_iso_date(it.get("date")), "class_id": cid(a, y, it.get("class_id", 0)),
            "lesson_mark_id": opt_cid(a, y, it.get("lesson_mark_id")),
            "lesson_alias_id": cid(a, y, alias_id) if alias_id is not None else None,
            "lesson_minutes_late": it.get("lesson_minutes_late"),
            "lesson_notes": it.get("lesson_notes"),
        })
    return {"student_lesson_marks": rows}


def flatten_session_marks(items, a, y, ctx):
    rows = []
    for it in items:
        alias_id = it.get("session_alias_id")
        rows.append({
            "data_set": y, "academy": a, "student_id": cid(a, y, it["student_id"]),
            "date": parse_iso_date(it.get("date")), "session": it.get("session"),
            "session_mark_id": opt_cid(a, y, it.get("session_mark_id")),
            "session_alias_id": cid(a, y, alias_id) if alias_id is not None else None,
            "session_minutes_late": it.get("session_minutes_late"),
            "session_notes": it.get("session_notes"),
        })
    return {"student_session_marks": rows}


def flatten_periods(items, a, y, ctx):
    rows = []
    for tt in items:
        for p in tt["periods"]:
            rows.append({
                "period_id": cid(a, y, p["id"]), "data_set": y, "academy": a,
                "timetable_id": cid(a, y, tt["id"]), "period_name": p.get("name"),
                "display_name": p.get("display_name"), "week_number": p.get("week", 0),
                "day_of_week": p.get("day_of_week"),
                # SQL stored these as Date (time truncated) — preserved for parity.
                "start": parse_iso_date(p.get("start")), "end": parse_iso_date(p.get("end")),
            })
    return {"periods": rows}


def flatten_tt_classes(items, a, y, ctx):
    return {"tt_classes": [{
        "class_id": cid(a, y, it["id"]), "data_set": y, "academy": a,
        "year_group": it.get("year_group"), "subject_code": it.get("subject_code"),
        "group_code": it.get("group_code"), "period_id": cid(a, y, it.get("period_id", 0)),
    } for it in items]}


def flatten_calendar(items, a, y, ctx):
    return {"calendar": [{
        "academy": a, "data_set": y, "date": parse_iso_date(it.get("date")),
        "timetable_id": it.get("timetable_id"), "week": it.get("week"),
        "day_type_code": it.get("day_type_code"),
    } for it in items]}


def flatten_beh_classifications(items, a, y, ctx):
    return {"beh_classifications": [{
        "beh_classification_id": it["id"], "data_set": y, "academy": a,
        "name": it.get("name"), "score": it.get("score", 0),
    } for it in items]}


def flatten_beh_event_types(items, a, y, ctx):
    return {"beh_event_types": [{
        "beh_event_type_id": it["id"], "data_set": y, "academy": a,
        "beh_classification_id": it.get("event_classification_id", 0),
        "code": it.get("code"), "name": it.get("name"), "alias": it.get("alias"),
        "significance": it.get("significance"), "prioritise": it.get("prioritise", False),
    } for it in items]}


def flatten_beh_events(items, a, y, ctx):
    events, students, incoming = [], [], []
    for it in items:
        # Every incoming id joins the merge's collision-delete list (GETBehEvents.cs), but
        # the event row itself is only stored when student_ids is present.
        incoming.append({"academy": a, "data_set": y, "date": ctx["date"],
                         "beh_event_id": it["id"]})
        if it.get("student_ids") is None:
            continue
        for stu in it["student_ids"]:
            students.append({"beh_event_id": it["id"], "student_id": cid(a, y, stu),
                             "g4s_stu_id": stu})
        events.append({
            "beh_event_id": it["id"], "data_set": y, "academy": a,
            "beh_event_type_id": it.get("event_type_id", 0),
            "event_date": parse_iso_ts(it.get("event_date")),
            "closed": it.get("closed", False), "cancelled": it.get("cancelled", False),
            "room_name": it.get("room_name"), "group_name": it.get("group_name"),
            "subject_code": it.get("subject_code"), "year_group": it.get("year_group"),
            "home_notes": it.get("home_notes"), "school_notes": it.get("school_notes"),
            "created_time_stamp": parse_iso_ts(it.get("created_timestamp")),
            "created_by_staff_id": it.get("created_by", 0),
            "modified_time_stamp": parse_iso_ts(it.get("modified_timestamp")),
            "modified_by_staff_id": it.get("modified_by", 0),
        })
    return {"beh_events": events, "beh_event_students": students,
            "beh_event_incoming_ids": incoming}


def flatten_staff(items, a, y, ctx):
    return {"staff": [{
        "staff_id": it["id"], "academy": a, "email_address": it.get("email_address"),
        "first_name": it.get("first_name"), "last_name": it.get("last_name"),
        "display_name": it.get("display_name"), "title": it.get("title"),
    } for it in items]}

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Endpoint registry — order matches Program.cs / GetAndStoreAllData.cs exactly.
# scope: "academy" (one call per academy), "year_group" (lowest..highest loop) or
# "date" (per-day loop with the .NET default windows).
# gate: academy config flag that must be true for the endpoint to run for that academy.

ENDPOINTS = [
    # --- Students ---
    dict(name="student_details", path="/customer/v1/academic-years/{academicYear}/students",
         envelope="students", tables=["students"], flatten=flatten_students, scope="academy"),
    dict(name="education_details",
         path="/customer/v1/academic-years/{academicYear}/students/education-details",
         envelope="students_and_education_details",
         tables=["education_details", "student_attributes", "student_attribute_values"],
         flatten=flatten_education_details, scope="academy"),
    dict(name="general_attributes",
         path="/customer/v1/academic-years/{academicYear}/students/attributes",
         envelope="students_and_attributes", tables=["attribute_types", "attribute_values"],
         flatten=make_flatten_attributes("General"), scope="academy", attribute_group="General"),
    dict(name="demographic_attributes",
         path="/customer/v1/academic-years/{academicYear}/students/attributes/demographic",
         envelope="students_and_attributes", tables=["attribute_types", "attribute_values"],
         flatten=make_flatten_attributes("Demographic"), scope="academy",
         attribute_group="Demographic"),
    dict(name="send_attributes",
         path="/customer/v1/academic-years/{academicYear}/students/attributes/send",
         envelope="students_and_attributes", tables=["attribute_types", "attribute_values"],
         flatten=make_flatten_attributes("Send"), scope="academy", attribute_group="Send"),
    dict(name="sensitive_attributes",
         path="/customer/v1/academic-years/{academicYear}/students/attributes/sensitive",
         envelope="students_and_attributes", tables=["attribute_types", "attribute_values"],
         flatten=make_flatten_attributes("Sensitive"), scope="academy",
         attribute_group="Sensitive"),
    # --- Teaching ---
    dict(name="departments", path="/customer/v1/academic-years/{academicYear}/teaching/departments",
         envelope="departments", tables=["departments"], flatten=flatten_departments,
         scope="academy"),
    dict(name="subjects", path="/customer/v1/academic-years/{academicYear}/teaching/subjects",
         envelope="subjects", tables=["subjects"], flatten=flatten_subjects, scope="academy"),
    dict(name="groups", path="/customer/v1/academic-years/{academicYear}/teaching/groups",
         envelope="groups", tables=["groups"], flatten=flatten_groups, scope="academy"),
    dict(name="group_students",
         path="/customer/v1/academic-years/{academicYear}/teaching/groups/students",
         envelope="groups_students", tables=["group_students"],
         flatten=flatten_group_students, scope="academy"),
    dict(name="teachers", path="/customer/v1/academic-years/{academicYear}/teaching/teachers",
         envelope="teacher", tables=["teachers"], flatten=flatten_teachers, scope="academy"),
    dict(name="group_teachers",
         path="/customer/v1/academic-years/{academicYear}/teaching/groups/teachers",
         envelope="group_teachers", tables=["group_teachers"],
         flatten=flatten_group_teachers, scope="academy"),
    # --- Assessment ---
    dict(name="markbooks", path="/customer/v1/academic-years/{academicYear}/assessment/markbooks",
         envelope="markbooks", tables=["marksheets", "markslots"],
         flatten=flatten_markbooks, scope="academy"),
    dict(name="marksheet_grades",
         path="/customer/v1/academic-years/{academicYear}/assessment/marksheet-grades",
         envelope="marksheets", tables=["marksheet_grades"],
         flatten=flatten_marksheet_grades, scope="academy"),
    dict(name="markslot_marks", path="/customer/v1/academic-years/{academicYear}/assessment/marks",
         envelope="markslots", tables=["markslot_marks"],
         flatten=flatten_markslot_marks, scope="academy"),
    # --- Attainment ---
    dict(name="prior_attainment",
         path="/customer/v1/academic-years/{academicYear}/attainment/prior-attainment",
         envelope="prior_attainment", tables=["prior_attainment"],
         flatten=flatten_prior_attainment, scope="academy"),
    dict(name="grade_names",
         path="/customer/v1/academic-years/{academicYear}/attainment/grade-types/year-group/{yearGroup}",
         envelope="GradesTypes", tables=["grade_names"], flatten=flatten_grade_names,
         scope="year_group"),
    dict(name="grades",
         path="/customer/v1/academic-years/{academicYear}/attainment/grades/year-group/{yearGroup}",
         envelope="grades", tables=["grades"], flatten=flatten_grades, scope="year_group"),
    dict(name="exam_results",
         path="/customer/v1/academic-years/{academicYear}/attainment/exam-results/year-group/{yearGroup}",
         envelope="ExamResults", tables=["exam_results"], flatten=flatten_exam_results,
         scope="year_group"),
    # --- Attendance ---
    dict(name="student_session_summaries",
         path="/customer/v1/academic-years/{academicYear}/attendance/student-session-summary",
         envelope="session_summary", tables=["student_session_summaries"],
         flatten=flatten_session_summaries, scope="academy"),
    dict(name="attendance_codes",
         path="/customer/v1/academic-years/{academicYear}/attendance/codes",
         envelope="AttendanceCodes", tables=["attendance_codes", "attendance_alias_codes"],
         flatten=flatten_attendance_codes, scope="academy"),
    dict(name="student_lesson_marks",
         path="/customer/v1/academic-years/{academicYear}/attendance/student-lesson-marks/date/{date}",
         envelope="StudentLessonMarks", tables=["student_lesson_marks"],
         flatten=flatten_lesson_marks, scope="date", gate="get_lesson_attendance",
         window=("attendance", -1, -1)),
    dict(name="student_session_marks",
         path="/customer/v1/academic-years/{academicYear}/attendance/student-session-marks/date/{date}",
         envelope="StudentSessionMarks", tables=["student_session_marks"],
         flatten=flatten_session_marks, scope="date", gate="get_session_attendance",
         window=("attendance", -7, 0)),
    # --- Timetables ---
    dict(name="periods", path="/customer/v1/academic-years/{academicYear}/timetables",
         envelope="Timetables", tables=["periods"], flatten=flatten_periods, scope="academy"),
    dict(name="tt_classes", path="/customer/v1/academic-years/{academicYear}/timetables/classes",
         envelope="classes", tables=["tt_classes"], flatten=flatten_tt_classes, scope="academy"),
    dict(name="calendar", path="/customer/v1/academic-years/{academicYear}/timetables/calendar",
         envelope="calendar", tables=["calendar"], flatten=flatten_calendar, scope="academy"),
    # --- Behaviour (all gated per academy by get_behaviour) ---
    dict(name="beh_classifications",
         path="/customer/v1/academic-years/{academicYear}/behaviour/classification",
         envelope="classification", tables=["beh_classifications"],
         flatten=flatten_beh_classifications, scope="academy", gate="get_behaviour"),
    dict(name="beh_event_types",
         path="/customer/v1/academic-years/{academicYear}/behaviour/event-types",
         envelope="eventtypes", tables=["beh_event_types"],
         flatten=flatten_beh_event_types, scope="academy", gate="get_behaviour"),
    dict(name="beh_events",
         path="/customer/v1/academic-years/{academicYear}/behaviour/events/date/{date}",
         envelope="behaviour_events",
         tables=["beh_events", "beh_event_students", "beh_event_incoming_ids"],
         flatten=flatten_beh_events, scope="date", gate="get_behaviour",
         window=("behaviour", -14, 0)),
    # --- Users ---
    dict(name="staff", path="/customer/v1/users/staff", envelope="staff", tables=["staff"],
         flatten=flatten_staff, scope="academy"),
]

# Run modes mirror Program.cs: no arg = FULL, ATT = attendance only, BEH = attendance then
# behaviour.
ATT_SET = {"student_session_summaries", "attendance_codes", "student_lesson_marks",
           "student_session_marks"}
BEH_SET = ATT_SET | {"beh_classifications", "beh_event_types", "beh_events"}
MODE_SETS = {"FULL": {ep["name"] for ep in ENDPOINTS}, "ATT": ATT_SET, "BEH": BEH_SET}

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Runner. Per endpoint: loop academies (and dates / year groups), pull + flatten, log a
# sync_result per call (failures are caught per scope and the run continues — one bad
# endpoint/academy never aborts the sync), then write each output table once.


def _window_dates(academy: dict, window) -> list:
    kind, default_from, default_to = window
    cfg_from = academy.get(f"{kind}_from")
    cfg_to = academy.get(f"{kind}_to")
    from_date = dt.date.fromisoformat(cfg_from) if cfg_from else TODAY + dt.timedelta(days=default_from)
    to_date = dt.date.fromisoformat(cfg_to) if cfg_to else TODAY + dt.timedelta(days=default_to)
    return [from_date + dt.timedelta(days=i) for i in range((to_date - from_date).days + 1)]


def _run_scope(ep, academy, year_group_int=None, year_group_str=None, date=None):
    a, y = academy["academy_code"], academy["current_academic_year"]
    ctx = {"year_group_int": year_group_int, "year_group_str": year_group_str, "date": date}
    mock_key = ep["name"] if MOCK_DIR else None
    try:
        items = api_get_all(get_api_key(academy), ep["path"], ep["envelope"], y,
                            year_group=year_group_str, date=date, mock_key=mock_key)
        out = ep["flatten"](items, a, y, ctx)
        log_sync_result(a, ep["path"], y, True, year_group=year_group_int)
        record_scope(ep["name"], a, y, ep["scope"], date=date, year_group=year_group_int,
                     attribute_group=ep.get("attribute_group"))
        return out
    except Exception as e:
        inner = repr(e.__cause__) if e.__cause__ else None
        log_sync_result(a, ep["path"], y, False, exception=str(e), inner_exception=inner)
        return None


def run_endpoint(ep):
    table_rows = {t: [] for t in ep["tables"]}
    for academy in ACADEMIES:
        if ep.get("gate") and not academy.get(ep["gate"]):
            continue
        if ep["scope"] == "academy":
            scopes = [dict()]
        elif ep["scope"] == "year_group":
            scopes = [dict(year_group_int=n, year_group_str="Reception" if n == 0 else str(n))
                      for n in range(academy["lowest_year"], academy["highest_year"] + 1)]
        else:  # date
            scopes = [dict(date=d) for d in _window_dates(academy, ep["window"])]
        for scope in scopes:
            out = _run_scope(ep, academy, **scope)
            if out is not None:
                for table in ep["tables"]:
                    table_rows[table].extend(out.get(table, []))

    if ep["name"] == "staff":
        # The .NET delete-by-id then insert sequence meant the LAST academy to run won any
        # shared staff id; replicate by keeping the last occurrence.
        last = {}
        for row in table_rows["staff"]:
            last[row["staff_id"]] = row
        table_rows["staff"] = list(last.values())

    for table in ep["tables"]:
        write_raw(table, table_rows[table])


clear_sync_scope()
selected = MODE_SETS[sync_mode]
for ep in ENDPOINTS:
    if ep["name"] in selected:
        print(f"== {ep['name']} ==")
        run_endpoint(ep)

flush_logs()

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Run summary.

failed = [r for r in _sync_results if not r["result"]]
print(f"Run {RUN_ID} ({sync_mode}) complete: {len(_sync_results)} calls, "
      f"{len(failed)} failed, {len(_sync_scopes)} scopes pulled.")
for r in failed:
    print(f"  FAILED {r['academy_code']} {r['end_point']} :: {r['exception']}")
print("Now run NB_G4S_Base_Merge to fold this pull into the base lakehouse.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
