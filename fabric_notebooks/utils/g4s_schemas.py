"""
Schema definitions for Go4Schools API endpoints.
These StructTypes map to the original C# DTO classes and provide:
- Schema validation at ingestion time
- Better query performance (no schema inference)
- Data quality enforcement
- Documentation of API contracts
"""

from pyspark.sql.types import (
    StructType, StructField, StringType, IntegerType, 
    BooleanType, DateType, TimestampType, ArrayType, DoubleType
)

# =============================================================================
# STUDENTS Domain Schemas
# =============================================================================

STUDENT_DETAILS_SCHEMA = StructType([
    StructField("id", IntegerType(), False),
    StructField("date_of_birth", StringType(), True),
    StructField("sex", StringType(), True),
    StructField("legal_first_name", StringType(), True),
    StructField("legal_last_name", StringType(), True),
    StructField("preferred_first_name", StringType(), True),
    StructField("preferred_last_name", StringType(), True),
    StructField("middle_names", StringType(), True),
])

EDUCATION_DETAILS_SCHEMA = StructType([
    StructField("student_id", IntegerType(), False),
    StructField("mis_id", StringType(), True),
    StructField("upn", StringType(), True),
    StructField("former_upn", StringType(), True),
    StructField("uln", StringType(), True),
    StructField("admission_number", StringType(), True),
    StructField("year_group", IntegerType(), True),
    StructField("registration_group", StringType(), True),
    StructField("house", StringType(), True),
])

ATTRIBUTE_VALUE_SCHEMA = StructType([
    StructField("student_id", IntegerType(), False),
    StructField("value_id", IntegerType(), True),
    StructField("attribute_id", IntegerType(), False),
    StructField("value", StringType(), True),
])

# =============================================================================
# TEACHING Domain Schemas
# =============================================================================

DEPARTMENT_SCHEMA = StructType([
    StructField("id", IntegerType(), False),
    StructField("name", StringType(), True),
    StructField("code", StringType(), True),
])

SUBJECT_SCHEMA = StructType([
    StructField("id", IntegerType(), False),
    StructField("name", StringType(), True),
    StructField("code", StringType(), True),
    StructField("department_id", IntegerType(), True),
])

GROUP_SCHEMA = StructType([
    StructField("id", IntegerType(), False),
    StructField("name", StringType(), True),
    StructField("code", StringType(), True),
    StructField("subject_id", IntegerType(), True),
])

GROUP_STUDENTS_SCHEMA = StructType([
    StructField("group_id", IntegerType(), False),
    StructField("student_ids", ArrayType(IntegerType()), True),
])

TEACHER_SCHEMA = StructType([
    StructField("id", IntegerType(), False),
    StructField("staff_code", StringType(), True),
    StructField("title", StringType(), True),
    StructField("first_name", StringType(), True),
    StructField("last_name", StringType(), True),
    StructField("middle_names", StringType(), True),
])

# =============================================================================
# ASSESSMENT Domain Schemas
# =============================================================================

MARKBOOK_SCHEMA = StructType([
    StructField("id", IntegerType(), False),
    StructField("name", StringType(), True),
    StructField("group_id", IntegerType(), True),
    StructField("staff_owner_id", IntegerType(), True),
])

MARKSHEET_GRADE_SCHEMA = StructType([
    StructField("id", IntegerType(), False),
    StructField("grades", ArrayType(
        StructType([
            StructField("student_id", IntegerType(), True),
            StructField("grade_id", IntegerType(), True),
            StructField("grade_name", StringType(), True),
            StructField("points", DoubleType(), True),
        ])
    ), True),
])

MARKSLOT_MARK_SCHEMA = StructType([
    StructField("id", IntegerType(), False),
    StructField("marks", ArrayType(
        StructType([
            StructField("student_id", IntegerType(), True),
            StructField("result", StringType(), True),
            StructField("comment", StringType(), True),
        ])
    ), True),
])

# =============================================================================
# ATTAINMENT Domain Schemas
# =============================================================================

PRIOR_ATTAINMENT_SCHEMA = StructType([
    StructField("student_id", IntegerType(), False),
    StructField("dataset_id", IntegerType(), True),
    StructField("dataset_name", StringType(), True),
    StructField("subject_id", IntegerType(), True),
    StructField("subject_name", StringType(), True),
    StructField("grade_id", IntegerType(), True),
    StructField("grade_name", StringType(), True),
    StructField("points", DoubleType(), True),
])

GRADE_NAME_SCHEMA = StructType([
    StructField("id", IntegerType(), False),
    StructField("name", StringType(), True),
    StructField("code", StringType(), True),
])

GRADE_SCHEMA = StructType([
    StructField("id", IntegerType(), False),
    StructField("name", StringType(), True),
    StructField("points", DoubleType(), True),
    StructField("grade_name_id", IntegerType(), True),
])

EXAM_RESULT_SCHEMA = StructType([
    StructField("student_id", IntegerType(), False),
    StructField("qualification_id", IntegerType(), True),
    StructField("qualification_name", StringType(), True),
    StructField("subject_id", IntegerType(), True),
    StructField("subject_name", StringType(), True),
    StructField("grade_id", IntegerType(), True),
    StructField("grade_name", StringType(), True),
    StructField("points", DoubleType(), True),
    StructField("year", IntegerType(), True),
])

# =============================================================================
# ATTENDANCE Domain Schemas
# =============================================================================

ATTENDANCE_CODE_SCHEMA = StructType([
    StructField("id", IntegerType(), False),
    StructField("code", StringType(), True),
    StructField("description", StringType(), True),
    StructField("category", StringType(), True),
    StructField("authorised", BooleanType(), True),
    StructField("present", BooleanType(), True),
])

STUDENT_LESSON_MARK_SCHEMA = StructType([
    StructField("student_id", IntegerType(), False),
    StructField("class_id", IntegerType(), True),
    StructField("date", StringType(), True),
    StructField("period_id", IntegerType(), True),
    StructField("attendance_code_id", IntegerType(), True),
    StructField("minutes_late", IntegerType(), True),
])

STUDENT_SESSION_MARK_SCHEMA = StructType([
    StructField("student_id", IntegerType(), False),
    StructField("date", StringType(), True),
    StructField("session", StringType(), True),
    StructField("attendance_code_id", IntegerType(), True),
    StructField("minutes_late", IntegerType(), True),
])

STUDENT_SESSION_SUMMARY_SCHEMA = StructType([
    StructField("student_id", IntegerType(), False),
    StructField("possible_sessions", IntegerType(), True),
    StructField("authorised_absences", IntegerType(), True),
    StructField("unauthorised_absences", IntegerType(), True),
    StructField("present", IntegerType(), True),
    StructField("late", IntegerType(), True),
])

# =============================================================================
# TIMETABLE Domain Schemas
# =============================================================================

CALENDAR_SCHEMA = StructType([
    StructField("date", StringType(), False),
    StructField("week_number", IntegerType(), True),
    StructField("week_letter", StringType(), True),
    StructField("term", IntegerType(), True),
    StructField("academic_year", StringType(), True),
])

PERIOD_SCHEMA = StructType([
    StructField("id", IntegerType(), False),
    StructField("name", StringType(), True),
    StructField("start_time", StringType(), True),
    StructField("end_time", StringType(), True),
])

TIMETABLE_CLASS_SCHEMA = StructType([
    StructField("id", IntegerType(), False),
    StructField("name", StringType(), True),
    StructField("group_id", IntegerType(), True),
    StructField("teacher_id", IntegerType(), True),
    StructField("room", StringType(), True),
    StructField("day", IntegerType(), True),
    StructField("period_id", IntegerType(), True),
])

# =============================================================================
# BEHAVIOUR Domain Schemas
# =============================================================================

BEHAVIOUR_CLASSIFICATION_SCHEMA = StructType([
    StructField("id", IntegerType(), False),
    StructField("name", StringType(), True),
    StructField("description", StringType(), True),
])

BEHAVIOUR_EVENT_TYPE_SCHEMA = StructType([
    StructField("id", IntegerType(), False),
    StructField("name", StringType(), True),
    StructField("classification_id", IntegerType(), True),
    StructField("points", IntegerType(), True),
    StructField("active", BooleanType(), True),
])

BEHAVIOUR_EVENT_SCHEMA = StructType([
    StructField("id", IntegerType(), False),
    StructField("student_id", IntegerType(), False),
    StructField("event_type_id", IntegerType(), True),
    StructField("date", StringType(), True),
    StructField("period_id", IntegerType(), True),
    StructField("recorded_by_staff_id", IntegerType(), True),
    StructField("comment", StringType(), True),
    StructField("points", IntegerType(), True),
])

# =============================================================================
# USERS Domain Schemas
# =============================================================================

STAFF_SCHEMA = StructType([
    StructField("id", IntegerType(), False),
    StructField("staff_code", StringType(), True),
    StructField("title", StringType(), True),
    StructField("first_name", StringType(), True),
    StructField("last_name", StringType(), True),
    StructField("middle_names", StringType(), True),
    StructField("email", StringType(), True),
])

# =============================================================================
# Schema Registry - Maps endpoint names to schemas
# =============================================================================

ENDPOINT_SCHEMAS = {
    # Students
    "student_details": STUDENT_DETAILS_SCHEMA,
    "education_details": EDUCATION_DETAILS_SCHEMA,
    "general_attributes": ATTRIBUTE_VALUE_SCHEMA,
    "demographic_attributes": ATTRIBUTE_VALUE_SCHEMA,
    "send_attributes": ATTRIBUTE_VALUE_SCHEMA,
    "sensitive_attributes": ATTRIBUTE_VALUE_SCHEMA,
    
    # Teaching
    "departments": DEPARTMENT_SCHEMA,
    "subjects": SUBJECT_SCHEMA,
    "groups": GROUP_SCHEMA,
    "group_students": GROUP_STUDENTS_SCHEMA,
    "teachers": TEACHER_SCHEMA,
    
    # Assessment
    "markbooks": MARKBOOK_SCHEMA,
    "marksheet_grades": MARKSHEET_GRADE_SCHEMA,
    "markslot_marks": MARKSLOT_MARK_SCHEMA,
    
    # Attainment
    "prior_attainment": PRIOR_ATTAINMENT_SCHEMA,
    "grade_names": GRADE_NAME_SCHEMA,
    "grades": GRADE_SCHEMA,
    "exam_results": EXAM_RESULT_SCHEMA,
    
    # Attendance
    "attendance_codes": ATTENDANCE_CODE_SCHEMA,
    "student_lesson_marks": STUDENT_LESSON_MARK_SCHEMA,
    "student_session_marks": STUDENT_SESSION_MARK_SCHEMA,
    "student_session_summaries": STUDENT_SESSION_SUMMARY_SCHEMA,
    
    # Timetable
    "calendar": CALENDAR_SCHEMA,
    "periods": PERIOD_SCHEMA,
    "timetable_classes": TIMETABLE_CLASS_SCHEMA,
    
    # Behaviour
    "behaviour_classifications": BEHAVIOUR_CLASSIFICATION_SCHEMA,
    "behaviour_event_types": BEHAVIOUR_EVENT_TYPE_SCHEMA,
    "behaviour_events": BEHAVIOUR_EVENT_SCHEMA,
    
    # Users
    "staff": STAFF_SCHEMA,
}


def get_schema_for_endpoint(endpoint_name: str) -> StructType:
    """
    Retrieve the schema for a given endpoint name.
    
    Args:
        endpoint_name: Name of the endpoint (e.g., 'student_details')
        
    Returns:
        StructType schema for the endpoint
        
    Raises:
        KeyError: If endpoint_name is not found in registry
    """
    if endpoint_name not in ENDPOINT_SCHEMAS:
        raise KeyError(f"No schema defined for endpoint: {endpoint_name}")
    
    return ENDPOINT_SCHEMAS[endpoint_name]


def add_metadata_to_schema(base_schema: StructType) -> StructType:
    """
    Add standard metadata fields to a schema for raw layer storage.
    
    Args:
        base_schema: The base schema from the API
        
    Returns:
        Extended schema with metadata fields
    """
    metadata_fields = [
        StructField("_academy_code", StringType(), False),
        StructField("_academic_year", StringType(), False),
        StructField("_endpoint", StringType(), False),
        StructField("_ingested_at", StringType(), False),
    ]
    
    return StructType(base_schema.fields + metadata_fields)
