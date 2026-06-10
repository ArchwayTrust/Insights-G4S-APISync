# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# # NB_G4S_Base_Merge
#
# Folds the latest `NB_G4S_Raw_Ingest` pull from the **raw** lakehouse into the **base**
# lakehouse. The base layer **persists every academic year** and is never fully rebuilt:
# each run deletes only the scopes the ingest pulled successfully (recorded in raw
# `g4s.sync_scope`) and inserts the fresh rows, replicating the .NET app's
# delete-then-bulk-insert behaviour including its EF cascade deletes:
#
# - plain scopes delete on `(academy, data_set)` (+ `attribute_group` / `nc_year` / `date`
#   where the .NET endpoint scoped finer);
# - cascade children (e.g. `marksheet_grades`, `attribute_values`, `group_students`) are
#   deleted via their composite-id prefix `<academy><year>-…` driven by the **parent**
#   endpoint's scope, and only re-inserted when the parent scope succeeded;
# - `beh_events` replicates the two-stage delete (per event date + incoming-id collisions)
#   with `beh_event_students` following the event ids;
# - `staff` replaces only the staff ids present in the pull.
#
# It also seeds the static `grade_types` reference table and rebuilds the three reporting
# tables that replace the old SQL views: `v_students`, `v_behaviour`,
# `v_session_attendance`.
#
# Run this immediately after `NB_G4S_Raw_Ingest` (chain the two notebook activities in a
# pipeline). Re-running against the same pull is idempotent. Set `dry_run = True` to print
# what would change without touching base.

# PARAMETERS CELL ********************

dry_run = False

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Environment and lakehouse addressing (same conventions as NB_G4S_Raw_Ingest).

import datetime as dt

from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType, DateType, FloatType, IntegerType, LongType,
    StringType, StructField, StructType, TimestampType,
)
from pyspark.sql.window import Window

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
    if SCHEMA_ENABLED:
        return f"`{STORE_WORKSPACE_NAME}`.`{lh_name}`.`g4s`.`{table}`"
    return f"`{STORE_WORKSPACE_NAME}`.`{lh_name}`.`dbo`.`g4s_{table}`"


def raw_table(table: str) -> str:
    return qualify(RAW_LH_NAME, table)


def base_table(table: str) -> str:
    return qualify(BASE_LH_NAME, table)


if SCHEMA_ENABLED:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{STORE_WORKSPACE_NAME}`.`{BASE_LH_NAME}`.`g4s`")

print(f"SCHEMA_ENABLED is set to {SCHEMA_ENABLED} so setting up as follows:")
print(f"raw:  {raw_table('<table>')}")
print(f"base: {base_table('<table>')}")
print(f"dry_run: {dry_run}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Base table schemas — the raw schemas plus the two regenerated identity columns
# (attribute_value_id / exam_result_id were SQL IDENTITY columns) and the static
# grade_types reference table. Keep in sync with TABLE_SCHEMAS in NB_G4S_Raw_Ingest.

_TYPES = {
    "string": StringType(), "int": IntegerType(), "long": LongType(),
    "bool": BooleanType(), "float": FloatType(), "date": DateType(), "ts": TimestampType(),
}


def _schema(*fields) -> StructType:
    return StructType([StructField(n, _TYPES[t], True) for n, t in fields])


BASE_SCHEMAS = {
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
        ("attribute_value_id", "int"), ("attribute_type_id", "string"), ("student_id", "string"),
        ("value", "string"), ("academic_year", "string"), ("date", "date")),
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
    "grade_types": _schema(("grade_type_id", "int"), ("name", "string")),
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
        ("exam_result_id", "int"), ("student_id", "string"), ("data_set", "string"),
        ("academy", "string"), ("nc_year", "int"), ("exam_academic_year", "string"),
        ("qan", "string"), ("qualification_title", "string"), ("exam_date", "date"),
        ("grade", "string"), ("ks123_literal", "string"), ("subject_id", "string")),
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
    "staff": _schema(
        ("staff_id", "int"), ("academy", "string"), ("email_address", "string"),
        ("first_name", "string"), ("last_name", "string"), ("display_name", "string"),
        ("title", "string")),
}

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Helpers: table creation, SQL building, scope access.


def ensure_table(table: str):
    cols = ", ".join(f"`{f.name}` {f.dataType.simpleString()}"
                     for f in BASE_SCHEMAS[table].fields)
    spark.sql(f"CREATE TABLE IF NOT EXISTS {base_table(table)} ({cols}) USING DELTA")


def q(value) -> str:
    """Quote a literal for Spark SQL."""
    return "'" + str(value).replace("'", "''") + "'"


def like_prefix(col: str, prefix: str) -> str:
    escaped = prefix.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")
    return f"`{col}` LIKE {q(escaped + '%')} ESCAPE '\\\\'"


def sql_delete(table: str, predicate: str) -> int:
    fqn = base_table(table)
    count = spark.sql(f"SELECT COUNT(*) FROM {fqn} WHERE {predicate}").first()[0]
    if not dry_run and count:
        spark.sql(f"DELETE FROM {fqn} WHERE {predicate}")
    return count


def append_to_base(table: str, df) -> int:
    count = df.count()
    if not dry_run and count:
        cols = [F.col(f"`{f.name}`") for f in BASE_SCHEMAS[table].fields]
        df.select(*cols).write.mode("append").format("delta").saveAsTable(base_table(table))
    return count


def next_id_base(table: str, id_col: str) -> int:
    return spark.sql(
        f"SELECT COALESCE(MAX(`{id_col}`), 0) FROM {base_table(table)}").first()[0]


def with_generated_id(df, id_col: str, start_after: int):
    window = Window.orderBy(F.monotonically_increasing_id())
    return df.withColumn(id_col, (F.row_number().over(window) + F.lit(start_after)).cast("int"))


# Load this run's successful scopes — the sole driver of every base deletion. Raw table
# contents are never used to infer scope, so an ATT/BEH run can never disturb tables a
# stale FULL pull left behind in raw.
SCOPES = [r.asDict() for r in spark.sql(f"SELECT * FROM {raw_table('sync_scope')}").collect()]
RUN_IDS = sorted({s["run_id"] for s in SCOPES})
if len(RUN_IDS) > 1:
    raise ValueError(f"sync_scope holds more than one run: {RUN_IDS} — rerun the ingest")
print(f"Scopes to merge: {len(SCOPES)} (run {RUN_IDS[0] if RUN_IDS else 'n/a — nothing to do'})")


def scopes_for(*endpoints) -> list:
    return [s for s in SCOPES if s["endpoint"] in endpoints]


for _table in BASE_SCHEMAS:
    ensure_table(_table)

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Static grade_types reference data — the EF Core seed from G4SContext.OnModelCreating.

GRADE_TYPES_SEED = [
    (1, "External target"), (2, "Teacher target"), (3, "Combined target"), (4, "Current"),
    (5, "Project"), (6, "Actual"), (7, "Honest"), (8, "Aspirational"),
    (9, "Additional target"), (10, "Baseline grade"),
]

if not dry_run:
    spark.createDataFrame(GRADE_TYPES_SEED, BASE_SCHEMAS["grade_types"]) \
        .write.mode("overwrite").format("delta").saveAsTable(base_table("grade_types"))
print("grade_types seeded (10 rows)")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Merge engine. Each entry replicates one .NET delete-then-insert (including the EF
# cascades). Kinds:
#   scope        delete on (academy, data_set) [+ nc_year / date] for the driver's scopes,
#                insert the full raw table (raw only ever holds successful scopes).
#   child_prefix cascade child: delete by composite-id prefix for the PARENT endpoint's
#                scopes; insert raw rows matching those prefixes (so a child pull that
#                succeeded while its parent failed is skipped, like the .NET PK violation).
#   attr_types / attr_values: the four attribute endpoints' scopes carry attribute_group;
#                delete/insert per (academy, data_set, group), values by id prefix
#                '<academy><year>-<Group>-', regenerating attribute_value_id.
#   staff_ids    delete only the staff ids present in the pull, then insert.
#   beh          two-stage behaviour event delete (per event date + incoming id
#                collisions), beh_event_students following the event ids.

ATTRIBUTE_ENDPOINTS = ("general_attributes", "demographic_attributes",
                       "send_attributes", "sensitive_attributes")

MERGE_SPEC = [
    dict(table="students", kind="scope", driver="student_details"),
    dict(table="education_details", kind="scope", driver="education_details"),
    dict(table="student_attributes", kind="child_prefix", driver="education_details",
         prefix_col="student_attribute_id"),
    dict(table="student_attribute_values", kind="child_prefix", driver="education_details",
         prefix_col="student_attribute_id"),
    dict(table="attribute_types", kind="attr_types"),
    dict(table="attribute_values", kind="attr_values"),
    dict(table="departments", kind="scope", driver="departments"),
    dict(table="subjects", kind="scope", driver="subjects"),
    dict(table="groups", kind="scope", driver="groups"),
    dict(table="group_students", kind="child_prefix", driver="groups", prefix_col="group_id"),
    dict(table="teachers", kind="scope", driver="teachers"),
    dict(table="group_teachers", kind="child_prefix", driver="groups", prefix_col="group_id"),
    dict(table="marksheets", kind="scope", driver="markbooks"),
    dict(table="markslots", kind="child_prefix", driver="markbooks", prefix_col="marksheet_id"),
    dict(table="marksheet_grades", kind="child_prefix", driver="markbooks",
         prefix_col="marksheet_id"),
    dict(table="markslot_marks", kind="child_prefix", driver="markbooks",
         prefix_col="markslot_id"),
    dict(table="prior_attainment", kind="scope", driver="prior_attainment"),
    dict(table="grade_names", kind="scope", driver="grade_names", extra="year_group"),
    dict(table="grades", kind="scope", driver="grades", extra="year_group"),
    dict(table="exam_results", kind="scope", driver="exam_results", extra="year_group",
         identity="exam_result_id"),
    dict(table="student_session_summaries", kind="scope", driver="student_session_summaries"),
    dict(table="attendance_codes", kind="scope", driver="attendance_codes"),
    dict(table="attendance_alias_codes", kind="child_prefix", driver="attendance_codes",
         prefix_col="attendance_alias_code_id"),
    dict(table="student_lesson_marks", kind="scope", driver="student_lesson_marks", extra="date"),
    dict(table="student_session_marks", kind="scope", driver="student_session_marks",
         extra="date"),
    dict(table="periods", kind="scope", driver="periods"),
    dict(table="tt_classes", kind="scope", driver="tt_classes"),
    dict(table="calendar", kind="scope", driver="calendar"),
    dict(table="beh_classifications", kind="scope", driver="beh_classifications"),
    dict(table="beh_event_types", kind="scope", driver="beh_event_types"),
    dict(table="beh_events", kind="beh"),
    dict(table="staff", kind="staff_ids", driver="staff"),
]


def _scope_predicate(scope, extra=None) -> str:
    parts = [f"`academy` = {q(scope['academy'])}", f"`data_set` = {q(scope['data_set'])}"]
    if extra == "year_group":
        parts.append(f"`nc_year` = {scope['year_group']}")
    elif extra == "date":
        parts.append(f"`date` = DATE'{scope['date'].isoformat()}'")
    return "(" + " AND ".join(parts) + ")"


def merge_scope(spec):
    scopes = scopes_for(spec["driver"])
    if not scopes:
        return None
    predicate = " OR ".join(_scope_predicate(s, spec.get("extra")) for s in scopes)
    deleted = sql_delete(spec["table"], predicate)
    src = spark.sql(f"SELECT * FROM {raw_table(spec['table'])}")
    if spec.get("identity"):
        src = with_generated_id(src, spec["identity"], next_id_base(spec["table"], spec["identity"]))
    inserted = append_to_base(spec["table"], src)
    return deleted, inserted


def merge_child_prefix(spec):
    scopes = scopes_for(spec["driver"])
    if not scopes:
        return None
    prefixes = sorted({f"{s['academy']}{s['data_set']}-" for s in scopes})
    predicate = " OR ".join(like_prefix(spec["prefix_col"], p) for p in prefixes)
    deleted = sql_delete(spec["table"], predicate)
    src = spark.sql(f"SELECT * FROM {raw_table(spec['table'])} WHERE {predicate}")
    inserted = append_to_base(spec["table"], src)
    return deleted, inserted


def merge_attr_types(spec):
    scopes = scopes_for(*ATTRIBUTE_ENDPOINTS)
    if not scopes:
        return None
    predicate = " OR ".join(
        f"(`academy` = {q(s['academy'])} AND `data_set` = {q(s['data_set'])}"
        f" AND `attribute_group` = {q(s['attribute_group'])})" for s in scopes)
    deleted = sql_delete("attribute_types", predicate)
    src = spark.sql(f"SELECT * FROM {raw_table('attribute_types')} WHERE {predicate}")
    inserted = append_to_base("attribute_types", src)
    return deleted, inserted


def merge_attr_values(spec):
    scopes = scopes_for(*ATTRIBUTE_ENDPOINTS)
    if not scopes:
        return None
    prefixes = sorted({f"{s['academy']}{s['data_set']}-{s['attribute_group']}-" for s in scopes})
    predicate = " OR ".join(like_prefix("attribute_type_id", p) for p in prefixes)
    deleted = sql_delete("attribute_values", predicate)
    src = spark.sql(f"SELECT * FROM {raw_table('attribute_values')} WHERE {predicate}")
    src = with_generated_id(src, "attribute_value_id",
                            next_id_base("attribute_values", "attribute_value_id"))
    inserted = append_to_base("attribute_values", src)
    return deleted, inserted


def merge_staff(spec):
    if not scopes_for("staff"):
        return None
    raw, base = raw_table("staff"), base_table("staff")
    deleted = spark.sql(
        f"SELECT COUNT(*) FROM {base} t WHERE EXISTS "
        f"(SELECT 1 FROM {raw} s WHERE s.`staff_id` = t.`staff_id`)").first()[0]
    if not dry_run:
        spark.sql(f"MERGE INTO {base} t USING {raw} s ON t.`staff_id` = s.`staff_id` "
                  "WHEN MATCHED THEN DELETE")
    inserted = append_to_base("staff", spark.sql(f"SELECT * FROM {raw}"))
    return deleted, inserted


def merge_beh_events(spec):
    scopes = scopes_for("beh_events")
    if not scopes:
        return None
    base_events = base_table("beh_events")
    base_students = base_table("beh_event_students")

    # Stage (a): events on the pulled dates. The .NET delete compared EventDate equal to
    # the date parameter (midnight) — preserved exactly; stage (b) catches everything else.
    date_pred = " OR ".join(
        f"(`academy` = {q(s['academy'])} AND `data_set` = {q(s['data_set'])}"
        f" AND `event_date` = TIMESTAMP'{s['date'].isoformat()} 00:00:00')" for s in scopes)
    # Stage (b): any event (any academy/year) whose id is in the incoming pull — including
    # events the ingest skipped because student_ids was null.
    ids_df = (spark.sql(f"SELECT `beh_event_id` FROM {base_events} WHERE {date_pred}")
              .union(spark.sql(f"SELECT `beh_event_id` FROM {raw_table('beh_event_incoming_ids')}"))
              .distinct())
    ids_df.createOrReplaceTempView("g4s_beh_ids_to_replace")
    deleted = spark.sql(
        f"SELECT COUNT(*) FROM {base_events} t WHERE EXISTS "
        "(SELECT 1 FROM g4s_beh_ids_to_replace i WHERE i.`beh_event_id` = t.`beh_event_id`)"
    ).first()[0]
    if not dry_run:
        # beh_event_students followed BehEvents via FK cascade — delete them first.
        spark.sql(f"MERGE INTO {base_students} t USING g4s_beh_ids_to_replace i "
                  "ON t.`beh_event_id` = i.`beh_event_id` WHEN MATCHED THEN DELETE")
        spark.sql(f"MERGE INTO {base_events} t USING g4s_beh_ids_to_replace i "
                  "ON t.`beh_event_id` = i.`beh_event_id` WHEN MATCHED THEN DELETE")
    inserted = append_to_base("beh_events", spark.sql(f"SELECT * FROM {raw_table('beh_events')}"))
    students_in = append_to_base("beh_event_students",
                                 spark.sql(f"SELECT * FROM {raw_table('beh_event_students')}"))
    print(f"  beh_event_students: +{students_in} rows")
    return deleted, inserted


_HANDLERS = {"scope": merge_scope, "child_prefix": merge_child_prefix,
             "attr_types": merge_attr_types, "attr_values": merge_attr_values,
             "staff_ids": merge_staff, "beh": merge_beh_events}

summary = []
for spec in MERGE_SPEC:
    result = _HANDLERS[spec["kind"]](spec)
    if result is None:
        continue
    deleted, inserted = result
    summary.append((spec["table"], deleted, inserted))
    print(f"{spec['table']}: -{deleted} +{inserted}")

if not summary:
    print("No scopes in raw sync_scope — nothing merged.")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Reporting tables replacing the SQL views (SQL Scripts/Create*View.sql), rebuilt from
# base (all academic years) each run. Columns are the views' columns in snake_case.

if not dry_run:

    # v_students — CreateStudentView.sql. The pivoted columns replace
    # udfAttributeValueLatest: latest attribute value per student ordered by value date
    # then academic year (SQL Server DESC puts NULLs last, matched explicitly here;
    # attribute_value_id breaks ties deterministically where TOP 1 was arbitrary).
    spark.sql(f"""
        CREATE OR REPLACE TABLE {base_table('v_students')} AS
        WITH latest AS (
            SELECT academy, data_set, student_id, attribute_name, value
            FROM (
                SELECT t.academy, t.data_set, v.student_id, t.attribute_name, v.value,
                       ROW_NUMBER() OVER (
                           PARTITION BY t.academy, t.data_set, t.attribute_name, v.student_id
                           ORDER BY v.`date` DESC NULLS LAST,
                                    v.academic_year DESC NULLS LAST,
                                    v.attribute_value_id DESC) AS rn
                FROM {base_table('attribute_values')} v
                JOIN {base_table('attribute_types')} t
                  ON v.attribute_type_id = t.attribute_type_id
                WHERE t.attribute_name IN (
                    'Enrollment status', 'Unique Learner Number', 'On roll', 'FSM',
                    'FSMEver6', 'Pupil Premium Indicator', 'Disadvantaged', 'Bursary',
                    'Looked After', 'Ever in Care', 'EAL', 'Ethnicity Code', 'SEN Code')
            ) ranked WHERE rn = 1
        ),
        attrs AS (
            SELECT academy, data_set, student_id,
                   MAX(CASE WHEN attribute_name = 'Enrollment status' THEN value END) AS enrollment_status_raw,
                   MAX(CASE WHEN attribute_name = 'Unique Learner Number' THEN value END) AS uln_raw,
                   MAX(CASE WHEN attribute_name = 'On roll' THEN value END) AS on_roll_raw,
                   MAX(CASE WHEN attribute_name = 'FSM' THEN value END) AS fsm_raw,
                   MAX(CASE WHEN attribute_name = 'FSMEver6' THEN value END) AS fsm_ever6_raw,
                   MAX(CASE WHEN attribute_name = 'Pupil Premium Indicator' THEN value END) AS pp_raw,
                   MAX(CASE WHEN attribute_name = 'Disadvantaged' THEN value END) AS disadvantaged_raw,
                   MAX(CASE WHEN attribute_name = 'Bursary' THEN value END) AS bursary_raw,
                   MAX(CASE WHEN attribute_name = 'Looked After' THEN value END) AS cla_raw,
                   MAX(CASE WHEN attribute_name = 'Ever in Care' THEN value END) AS ever_in_care_raw,
                   MAX(CASE WHEN attribute_name = 'EAL' THEN value END) AS eal_raw,
                   MAX(CASE WHEN attribute_name = 'Ethnicity Code' THEN value END) AS ethnicity_raw,
                   MAX(CASE WHEN attribute_name = 'SEN Code' THEN value END) AS sen_code_raw
            FROM latest
            GROUP BY academy, data_set, student_id
        )
        SELECT
            s.academy,
            s.data_set,
            s.student_id,
            e.upn,
            s.preferred_first_name AS first_name,
            s.preferred_last_name AS last_name,
            s.sex AS gender,
            s.date_of_birth,
            CASE WHEN e.registration_group = 'Ducklings' THEN -1
                 WHEN e.nc_year = 'Reception' THEN 0
                 ELSE TRY_CAST(e.nc_year AS INT)
            END AS nc_year,
            e.registration_group AS reg_group,
            e.admission_date,
            e.leaving_date,
            a.enrollment_status_raw AS enrollment_status,
            a.uln_raw AS uln,
            CASE WHEN a.on_roll_raw = 'True' THEN true ELSE false END AS on_roll,
            CASE WHEN a.fsm_raw = 'True' THEN 'FSM' ELSE 'Not FSM' END AS fsm,
            CASE WHEN a.fsm_ever6_raw = 'True' THEN 'FSM Ever6' ELSE 'Not FSM Ever6' END AS fsm_ever6,
            CASE WHEN a.pp_raw = 'True' THEN 'PP' ELSE 'Not PP' END AS pp,
            CASE WHEN a.disadvantaged_raw = 'True' THEN 'Disadvantaged' ELSE 'Not Disadvantaged' END AS disadvantaged,
            CASE WHEN a.bursary_raw = 'True' THEN 'Bursary' ELSE 'No Bursary' END AS bursary,
            CASE WHEN a.cla_raw = 'True' THEN 'CLA' ELSE 'Not CLA' END AS child_looked_after,
            CASE WHEN a.ever_in_care_raw = 'True' THEN 'Ever In Care' ELSE 'Not Ever in Care' END AS ever_in_care,
            CASE WHEN a.eal_raw = 'True' THEN 'EAL' ELSE 'Not EAL' END AS eal,
            a.ethnicity_raw AS ethnicity,
            a.sen_code_raw AS sen_code,
            p.value AS ks2_band
        FROM {base_table('students')} s
        LEFT JOIN {base_table('education_details')} e ON e.student_id = s.student_id
        LEFT JOIN attrs a ON a.academy = s.academy AND a.data_set = s.data_set
                         AND a.student_id = s.student_id
        LEFT JOIN {base_table('prior_attainment')} p ON s.student_id = p.student_id
                                                    AND p.name = 'Prior Attainment (KS2)'
    """)
    print("v_students rebuilt")

    # v_behaviour — CreateBehaviourView.sql.
    spark.sql(f"""
        CREATE OR REPLACE TABLE {base_table('v_behaviour')} AS
        SELECT
            e.beh_event_id,
            e.academy,
            e.data_set,
            st.student_id,
            ed.upn,
            st.preferred_first_name AS student_first_name,
            st.preferred_last_name AS student_last_name,
            bc.name AS behaviour_class,
            bc.score,
            et.code AS event_code,
            et.name AS event_type,
            e.subject_code,
            sb.name AS subject,
            e.year_group,
            e.group_name,
            et.significance,
            e.event_date,
            s.first_name AS created_by_first_name,
            s.last_name AS created_by_last_name,
            s.email_address AS created_by_email,
            e.school_notes,
            e.cancelled,
            e.closed
        FROM {base_table('beh_events')} e
        LEFT JOIN {base_table('beh_event_types')} et
               ON et.beh_event_type_id = e.beh_event_type_id
        LEFT JOIN {base_table('beh_classifications')} bc
               ON bc.beh_classification_id = et.beh_classification_id
        LEFT JOIN {base_table('staff')} s ON s.staff_id = e.created_by_staff_id
        LEFT JOIN {base_table('beh_event_students')} bs ON bs.beh_event_id = e.beh_event_id
        LEFT JOIN {base_table('students')} st ON bs.student_id = st.student_id
        LEFT JOIN {base_table('education_details')} ed ON ed.student_id = st.student_id
        LEFT JOIN {base_table('subjects')} sb ON sb.academy = e.academy
                                             AND sb.code = e.subject_code
                                             AND sb.year_group = e.year_group
                                             AND sb.data_set = e.data_set
    """)
    print("v_behaviour rebuilt")

    # v_session_attendance — CreateSessionAttendanceView.sql (academy/data_set come from
    # education_details, exactly as the SQL view did).
    spark.sql(f"""
        CREATE OR REPLACE TABLE {base_table('v_session_attendance')} AS
        SELECT
            ed.data_set,
            ed.academy,
            s.student_id,
            ed.upn,
            sm.`date`,
            sm.`session`,
            ac.code AS attendance_code,
            ac.attendance_label AS attendance_code_label,
            aac.alias_code AS attendance_alias_code,
            aac.label AS attendance_alias_code_label,
            sm.session_minutes_late,
            sm.session_notes
        FROM {base_table('student_session_marks')} sm
        LEFT JOIN {base_table('students')} s ON s.student_id = sm.student_id
        LEFT JOIN {base_table('education_details')} ed ON s.student_id = ed.student_id
        LEFT JOIN {base_table('attendance_codes')} ac
               ON sm.session_mark_id = ac.attendance_code_id
        LEFT JOIN {base_table('attendance_alias_codes')} aac
               ON sm.session_alias_id = aac.attendance_alias_code_id
    """)
    print("v_session_attendance rebuilt")
else:
    print("dry_run — view tables not rebuilt")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Merge summary.

print(f"{'TABLE':35} {'DELETED':>10} {'INSERTED':>10}")
for table, deleted, inserted in summary:
    print(f"{table:35} {deleted:>10} {inserted:>10}")
print(("DRY RUN — no changes applied." if dry_run else "Base merge complete."))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
