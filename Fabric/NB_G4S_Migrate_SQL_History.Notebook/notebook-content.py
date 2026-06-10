# Fabric notebook source

# METADATA ********************

# META {
# META   "kernel_info": {
# META     "name": "synapse_pyspark"
# META   },
# META   "dependencies": {}
# META }

# MARKDOWN ********************

# # NB_G4S_Migrate_SQL_History
#
# **One-off** migration of the historic on-prem SQL Server `g4s.*` tables into the base
# lakehouse, renaming every PascalCase table/column to the snake_case convention used by
# the new sync.
#
# **Before running**: copy the SQL tables into the **raw** lakehouse with a Fabric pipeline
# Copy activity through the on-premises data gateway (see `Fabric/README.md` for the
# runbook). Land them with their original PascalCase names, no transformation:
# - schema-enabled raw lakehouse → land as `<source_schema>.<TableName>` (default schema
#   `migration`, e.g. `migration.Students`);
# - legacy lakehouse → land as `dbo.<source_prefix><TableName>` and set `source_prefix`
#   (e.g. `g4s_migration_Students`).
#
# The merge is **idempotent**: keyed tables delete base rows whose natural key appears in
# the staged copy before appending, so re-running converges to the same state. The two
# identity tables (`AttributeValues`, `ExamResults`) have no stable natural key — they are
# **overwritten** from the SQL snapshot (the SQL data is authoritative for history) when
# `overwrite_identity_tables` is true. `GradeTypes` is skipped (static seed owned by
# `NB_G4S_Base_Merge`). `SyncResults` history is appended to **raw** `g4s.sync_results`
# with `run_id = 'sql-migration'` when `include_sync_results` is true.
#
# Run order: land SQL copies → run this notebook → verify counts → enable the scheduled
# ingest/merge pipelines → decommission the Task Scheduler job after a parallel-run window.

# PARAMETERS CELL ********************

source_schema = "migration"        # schema in the raw lakehouse where the SQL copies landed
source_prefix = ""                 # table-name prefix used by the Copy activity, if any
overwrite_identity_tables = True   # AttributeValues / ExamResults: overwrite base from SQL
include_sync_results = True        # append historic SyncResults into raw g4s.sync_results
dry_run = False

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Environment (same conventions as NB_G4S_Raw_Ingest / NB_G4S_Base_Merge).

from pyspark.sql import functions as F
from pyspark.sql.types import (
    BooleanType, DateType, FloatType, IntegerType, LongType,
    StringType, StructField, StructType, TimestampType,
)

from notebookutils import variableLibrary

vl = variableLibrary.getLibrary("VL_CORE")

SCHEMA_ENABLED = vl.getVariable("SCHEMA_ENABLED")
STORE_WORKSPACE_NAME = vl.getVariable("STORE_WORKSPACE_NAME")
RAW_LH_NAME = vl.getVariable("RAW_LH_NAME")
BASE_LH_NAME = vl.getVariable("BASE_LH_NAME")


def qualify(lh_name: str, table: str) -> str:
    if SCHEMA_ENABLED:
        return f"`{STORE_WORKSPACE_NAME}`.`{lh_name}`.`g4s`.`{table}`"
    return f"`{STORE_WORKSPACE_NAME}`.`{lh_name}`.`dbo`.`g4s_{table}`"


def base_table(table: str) -> str:
    return qualify(BASE_LH_NAME, table)


def raw_table(table: str) -> str:
    return qualify(RAW_LH_NAME, table)


def source_table(pascal_name: str) -> str:
    schema = source_schema if SCHEMA_ENABLED else "dbo"
    return (f"`{STORE_WORKSPACE_NAME}`.`{RAW_LH_NAME}`.`{schema}`."
            f"`{source_prefix}{pascal_name}`")


if SCHEMA_ENABLED:
    spark.sql(f"CREATE SCHEMA IF NOT EXISTS `{STORE_WORKSPACE_NAME}`.`{BASE_LH_NAME}`.`g4s`")

print(f"SCHEMA_ENABLED is set to {SCHEMA_ENABLED} so setting up as follows:")
print(f"source: {source_table('<TableName>')}")
print(f"base:   {base_table('<table>')}")
print(f"dry_run: {dry_run}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Target schemas — keep in sync with BASE_SCHEMAS in NB_G4S_Base_Merge (the staged SQL
# copies are cast to these types: nvarchar -> string, int -> int, bit -> boolean,
# real -> float, Date -> date, datetime2 -> timestamp).

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
    "sync_results": _schema(
        ("sync_result_id", "long"), ("logged_at", "ts"), ("academy_code", "string"),
        ("end_point", "string"), ("data_set", "string"), ("year_group", "int"), ("result", "bool"),
        ("exception", "string"), ("inner_exception", "string"), ("run_id", "string"),
        ("sync_mode", "string")),
}

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Migration spec: SQL table -> (target table, key columns for the idempotent delete,
# PascalCase -> snake_case column map). key=None means identity table (no stable key):
# overwritten from the SQL snapshot. GradeTypes is intentionally absent (static seed).

MIGRATION_SPEC = [
    ("Students", "students", ["student_id"], {
        "StudentId": "student_id", "G4SStuId": "g4s_stu_id", "DataSet": "data_set",
        "Academy": "academy", "DateOfBirth": "date_of_birth", "Sex": "sex",
        "LegalFirstName": "legal_first_name", "LegalLastName": "legal_last_name",
        "PreferredFirstName": "preferred_first_name", "PreferredLastName": "preferred_last_name",
        "MiddleNames": "middle_names"}),
    ("EducationDetails", "education_details", ["student_id"], {
        "StudentId": "student_id", "G4SStuId": "g4s_stu_id", "DataSet": "data_set",
        "Academy": "academy", "UPN": "upn", "FormerUPN": "former_upn", "NCYear": "nc_year",
        "RegistrationGroup": "registration_group", "House": "house",
        "AdmissionDate": "admission_date", "LeavingDate": "leaving_date",
        "RemovedFromSource": "removed_from_source"}),
    ("StudentAttributes", "student_attributes", ["student_attribute_id"], {
        "StudentAttributeId": "student_attribute_id", "StudentId": "student_id",
        "G4SStuId": "g4s_stu_id", "AttributeId": "attribute_id", "Code": "code",
        "Name": "name", "IsSystem": "is_system"}),
    ("StudentAttributeValues", "student_attribute_values", ["student_attribute_id"], {
        "StudentAttributeId": "student_attribute_id", "Value": "value",
        "AcademicYear": "academic_year", "Date": "date"}),
    ("AttributeTypes", "attribute_types", ["attribute_type_id"], {
        "AttributeTypeId": "attribute_type_id", "G4SAttributeId": "g4s_attribute_id",
        "DataSet": "data_set", "Academy": "academy", "AttributeGroup": "attribute_group",
        "Code": "code", "AttributeName": "attribute_name", "IsSystem": "is_system"}),
    ("AttributeValues", "attribute_values", None, {
        "AttributeValueId": "attribute_value_id", "AttributeTypeId": "attribute_type_id",
        "StudentId": "student_id", "Value": "value", "AcademicYear": "academic_year",
        "Date": "date"}),
    ("Departments", "departments", ["department_id"], {
        "DepartmentId": "department_id", "DataSet": "data_set", "Academy": "academy",
        "G4SDepartmentId": "g4s_department_id", "Name": "name"}),
    ("Subjects", "subjects", ["subject_id"], {
        "SubjectId": "subject_id", "G4SSubjectId": "g4s_subject_id", "DataSet": "data_set",
        "Academy": "academy", "Name": "name", "Code": "code", "YearGroup": "year_group",
        "DepartmentId": "department_id", "QAN": "qan",
        "QualificationTitle": "qualification_title",
        "QualificationSchemeName": "qualification_scheme_name",
        "IncludeInStats": "include_in_stats"}),
    ("Groups", "groups", ["group_id"], {
        "GroupId": "group_id", "DataSet": "data_set", "Academy": "academy", "Name": "name",
        "Code": "code", "SubjectId": "subject_id"}),
    ("GroupStudents", "group_students", ["group_id", "student_id"], {
        "GroupId": "group_id", "StudentId": "student_id"}),
    ("GroupTeachers", "group_teachers", ["group_id", "teacher_id"], {
        "GroupId": "group_id", "TeacherId": "teacher_id"}),
    ("Teachers", "teachers", ["teacher_id"], {
        "TeacherId": "teacher_id", "G4STeacherId": "g4s_teacher_id", "DataSet": "data_set",
        "Academy": "academy", "Title": "title", "FirstName": "first_name",
        "LastName": "last_name", "PreferredFirstName": "preferred_first_name",
        "PreferredLastName": "preferred_last_name", "Initials": "initials", "Code": "code"}),
    ("Marksheets", "marksheets", ["marksheet_id"], {
        "MarksheetId": "marksheet_id", "SubjectId": "subject_id", "DataSet": "data_set",
        "Academy": "academy", "Name": "name"}),
    ("MarksheetGrades", "marksheet_grades", ["student_id", "marksheet_id"], {
        "StudentId": "student_id", "MarksheetId": "marksheet_id", "Grade": "grade",
        "Alias": "alias"}),
    ("Markslots", "markslots", ["markslot_id"], {
        "MarkslotId": "markslot_id", "MarksheetId": "marksheet_id", "Name": "name",
        "MaxMarks": "max_marks"}),
    ("MarkslotMarks", "markslot_marks", ["student_id", "markslot_id"], {
        "StudentId": "student_id", "MarkslotId": "markslot_id", "Grade": "grade",
        "Alias": "alias", "Mark": "mark"}),
    ("PriorAttainment", "prior_attainment", ["student_id", "code"], {
        "StudentId": "student_id", "Code": "code", "DataSet": "data_set", "Academy": "academy",
        "Name": "name", "Value": "value", "ValueAcademicYear": "value_academic_year",
        "ValueDate": "value_date"}),
    ("Grades", "grades", ["student_id", "grade_type_id", "subject_id"], {
        "StudentId": "student_id", "GradeTypeId": "grade_type_id", "SubjectId": "subject_id",
        "DataSet": "data_set", "Academy": "academy", "NCYear": "nc_year", "Name": "name",
        "Alias": "alias"}),
    ("GradeNames", "grade_names", ["grade_name_id"], {
        "GradeNameId": "grade_name_id", "GradeTypeId": "grade_type_id", "DataSet": "data_set",
        "Academy": "academy", "NCYear": "nc_year", "Name": "name", "ShortName": "short_name",
        "Description": "description", "PreferredProgressGrade": "preferred_progress_grade",
        "PreferredTargetGrade": "preferred_target_grade"}),
    ("ExamResults", "exam_results", None, {
        "ExamResultId": "exam_result_id", "StudentId": "student_id", "DataSet": "data_set",
        "Academy": "academy", "NCYear": "nc_year", "ExamAcademicYear": "exam_academic_year",
        "QAN": "qan", "QualificationTitle": "qualification_title", "ExamDate": "exam_date",
        "Grade": "grade", "KS123Literal": "ks123_literal", "SubjectId": "subject_id"}),
    ("StudentSessionSummaries", "student_session_summaries", ["student_id"], {
        "StudentId": "student_id", "G4SStuId": "g4s_stu_id", "DataSet": "data_set",
        "Academy": "academy", "PossibleSessions": "possible_sessions", "Present": "present",
        "ApprovedEducationalActivity": "approved_educational_activity",
        "AuthorisedAbsence": "authorised_absence",
        "UnauthorisedAbsence": "unauthorised_absence",
        "AttendanceNotRequired": "attendance_not_required", "MissingMark": "missing_mark",
        "Late": "late"}),
    ("AttendanceCodes", "attendance_codes", ["attendance_code_id"], {
        "AttendanceCodeId": "attendance_code_id", "DataSet": "data_set", "Academy": "academy",
        "Code": "code", "AttendanceLabel": "attendance_label",
        "AttendanceOfficerOnly": "attendance_officer_only", "ProtectAO": "protect_ao",
        "ProtectSM": "protect_sm", "ProtectBM": "protect_bm"}),
    ("AttendanceAliasCodes", "attendance_alias_codes", ["attendance_alias_code_id"], {
        "AttendanceAliasCodeId": "attendance_alias_code_id",
        "AttendanceCodeId": "attendance_code_id", "AliasCode": "alias_code", "Label": "label"}),
    ("StudentLessonMarks", "student_lesson_marks", ["student_id", "date", "class_id"], {
        "StudentId": "student_id", "Date": "date", "ClassId": "class_id", "DataSet": "data_set",
        "Academy": "academy", "LessonMarkId": "lesson_mark_id",
        "LessonAliasId": "lesson_alias_id", "LessonMinutesLate": "lesson_minutes_late",
        "LessonNotes": "lesson_notes"}),
    ("StudentSessionMarks", "student_session_marks", ["student_id", "date", "session"], {
        "StudentId": "student_id", "Date": "date", "Session": "session", "DataSet": "data_set",
        "Academy": "academy", "SessionMarkId": "session_mark_id",
        "SessionAliasId": "session_alias_id", "SessionMinutesLate": "session_minutes_late",
        "SessionNotes": "session_notes"}),
    ("Periods", "periods", ["period_id"], {
        "PeriodId": "period_id", "DataSet": "data_set", "Academy": "academy",
        "TimetableId": "timetable_id", "PeriodName": "period_name",
        "DisplayName": "display_name", "WeekNumber": "week_number", "DayOfWeek": "day_of_week",
        "Start": "start", "End": "end"}),
    ("TTClasses", "tt_classes", ["class_id"], {
        "ClassId": "class_id", "DataSet": "data_set", "Academy": "academy",
        "YearGroup": "year_group", "SubjectCode": "subject_code", "GroupCode": "group_code",
        "PeriodId": "period_id"}),
    ("Calendar", "calendar", ["academy", "data_set", "date"], {
        "Academy": "academy", "DataSet": "data_set", "Date": "date",
        "TimetableId": "timetable_id", "Week": "week", "DayTypeCode": "day_type_code"}),
    ("BehClassifications", "beh_classifications", ["beh_classification_id"], {
        "BehClassificationId": "beh_classification_id", "DataSet": "data_set",
        "Academy": "academy", "Name": "name", "Score": "score"}),
    ("BehEventTypes", "beh_event_types", ["beh_event_type_id"], {
        "BehEventTypeId": "beh_event_type_id", "DataSet": "data_set", "Academy": "academy",
        "BehClassificationId": "beh_classification_id", "Code": "code", "Name": "name",
        "Alias": "alias", "Significance": "significance", "Prioritise": "prioritise"}),
    ("BehEvents", "beh_events", ["beh_event_id"], {
        "BehEventId": "beh_event_id", "DataSet": "data_set", "Academy": "academy",
        "BehEventTypeId": "beh_event_type_id", "EventDate": "event_date", "Closed": "closed",
        "Cancelled": "cancelled", "RoomName": "room_name", "GroupName": "group_name",
        "SubjectCode": "subject_code", "YearGroup": "year_group", "HomeNotes": "home_notes",
        "SchoolNotes": "school_notes", "CreatedTimeStamp": "created_time_stamp",
        "CreatedByStaffId": "created_by_staff_id", "ModifiedTimeStamp": "modified_time_stamp",
        "ModifiedByStaffId": "modified_by_staff_id"}),
    ("BehEventStudents", "beh_event_students", ["beh_event_id", "student_id"], {
        "BehEventId": "beh_event_id", "StudentId": "student_id", "G4SStuId": "g4s_stu_id"}),
    ("Staff", "staff", ["staff_id"], {
        "StaffId": "staff_id", "Academy": "academy", "EmailAddress": "email_address",
        "FirstName": "first_name", "LastName": "last_name", "DisplayName": "display_name",
        "Title": "title"}),
]

SYNC_RESULTS_MAP = {
    "SyncResultId": "sync_result_id", "LoggedAt": "logged_at", "AcademyCode": "academy_code",
    "EndPoint": "end_point", "DataSet": "data_set", "YearGroup": "year_group",
    "Result": "result", "Exception": "exception", "InnerException": "inner_exception",
}

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Migration engine: read each landed SQL copy, rename + cast to the target schema, delete
# overlapping base rows by natural key (or overwrite the identity tables), then append.


def ensure_table(table: str):
    cols = ", ".join(f"`{f.name}` {f.dataType.simpleString()}"
                     for f in BASE_SCHEMAS[table].fields)
    spark.sql(f"CREATE TABLE IF NOT EXISTS {base_table(table)} ({cols}) USING DELTA")


def stage(pascal_name: str, target: str, column_map: dict):
    src = spark.sql(f"SELECT * FROM {source_table(pascal_name)}")
    target_fields = {f.name: f for f in BASE_SCHEMAS[target].fields}
    cols = [F.col(f"`{pascal}`").cast(target_fields[snake].dataType).alias(snake)
            for pascal, snake in column_map.items()]
    return src.select(*cols)


def migrate_keyed(target: str, keys: list, staged) -> tuple:
    ensure_table(target)
    staged.createOrReplaceTempView("g4s_migration_staged")
    on = " AND ".join(f"t.`{k}` = s.`{k}`" for k in keys)
    deleted = spark.sql(
        f"SELECT COUNT(*) FROM {base_table(target)} t WHERE EXISTS "
        f"(SELECT 1 FROM g4s_migration_staged s WHERE {on})").first()[0]
    if not dry_run:
        spark.sql(f"MERGE INTO {base_table(target)} t USING g4s_migration_staged s "
                  f"ON {on} WHEN MATCHED THEN DELETE")
        cols = [F.col(f"`{f.name}`") for f in BASE_SCHEMAS[target].fields]
        staged.select(*cols).write.mode("append").format("delta") \
            .saveAsTable(base_table(target))
    return deleted, staged.count()


def migrate_overwrite(target: str, staged) -> tuple:
    ensure_table(target)
    deleted = spark.sql(f"SELECT COUNT(*) FROM {base_table(target)}").first()[0]
    if not dry_run:
        cols = [F.col(f"`{f.name}`") for f in BASE_SCHEMAS[target].fields]
        staged.select(*cols).write.mode("overwrite").format("delta") \
            .saveAsTable(base_table(target))
    return deleted, staged.count()


results = []
for pascal_name, target, keys, column_map in MIGRATION_SPEC:
    try:
        staged = stage(pascal_name, target, column_map)
        staged.first()  # force resolution so a missing source fails here
    except Exception as e:
        results.append((pascal_name, target, "SKIPPED (source not found)", 0, 0))
        print(f"SKIP {pascal_name}: {e}")
        continue
    if keys is None:
        if not overwrite_identity_tables:
            results.append((pascal_name, target, "SKIPPED (identity, overwrite disabled)", 0, 0))
            continue
        deleted, inserted = migrate_overwrite(target, staged)
        action = "overwritten"
    else:
        deleted, inserted = migrate_keyed(target, keys, staged)
        action = "merged"
    results.append((pascal_name, target, action, deleted, inserted))
    print(f"{pascal_name} -> {target}: {action}, -{deleted} +{inserted}")

# Historic SyncResults go to RAW g4s.sync_results (the new sync's append-only log).
if include_sync_results:
    try:
        src = spark.sql(f"SELECT * FROM {source_table('SyncResults')}")
        target_fields = {f.name: f for f in BASE_SCHEMAS["sync_results"].fields}
        cols = [F.col(f"`{p}`").cast(target_fields[s].dataType).alias(s)
                for p, s in SYNC_RESULTS_MAP.items()]
        staged = (src.select(*cols)
                  .withColumn("run_id", F.lit("sql-migration"))
                  .withColumn("sync_mode", F.lit("MIGRATION")))
        count = staged.count()
        if not dry_run:
            sel = [F.col(f"`{f.name}`") for f in BASE_SCHEMAS["sync_results"].fields]
            staged.select(*sel).write.mode("append").format("delta") \
                .saveAsTable(raw_table("sync_results"))
        results.append(("SyncResults", "sync_results (raw)", "appended", 0, count))
        print(f"SyncResults -> raw sync_results: +{count}")
    except Exception as e:
        print(f"SKIP SyncResults: {e}")

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }

# CELL ********************

# Verification: per-(academy, data_set) row counts, source vs base, for every migrated
# table that carries those columns. Counts must match exactly for the migrated scopes.

print(f"{'SOURCE':28} {'TARGET':28} {'ACTION':12} {'-':>9} {'+':>9}")
for pascal_name, target, action, deleted, inserted in results:
    print(f"{pascal_name:28} {target:28} {action:12} {deleted:>9} {inserted:>9}")

if not dry_run:
    print("\nScope-level parity (source vs base):")
    for pascal_name, target, action, _, _ in results:
        if action.startswith("SKIPPED") or target.endswith("(raw)"):
            continue
        cols = {f.name for f in BASE_SCHEMAS[target].fields}
        if not {"academy", "data_set"} <= cols:
            continue
        mismatches = spark.sql(f"""
            SELECT COALESCE(s.Academy, b.academy) AS academy,
                   COALESCE(s.DataSet, b.data_set) AS data_set,
                   COALESCE(s.n, 0) AS source_rows, COALESCE(b.n, 0) AS base_rows
            FROM (SELECT Academy, DataSet, COUNT(*) n FROM {source_table(pascal_name)}
                  GROUP BY Academy, DataSet) s
            FULL OUTER JOIN (SELECT academy, data_set, COUNT(*) n FROM {base_table(target)}
                  GROUP BY academy, data_set) b
              ON s.Academy = b.academy AND s.DataSet = b.data_set
            WHERE COALESCE(s.n, 0) <> COALESCE(b.n, 0)
        """).collect()
        status = "OK" if not mismatches else f"{len(mismatches)} scope(s) differ"
        print(f"  {target:30} {status}")
        for m in mismatches[:10]:
            print(f"    {m['academy']}/{m['data_set']}: source={m['source_rows']} base={m['base_rows']}")
print("Migration " + ("dry run complete — nothing written." if dry_run else "complete."))

# METADATA ********************

# META {
# META   "language": "python",
# META   "language_group": "synapse_pyspark"
# META }
