# Schema Definitions Reference

## Overview

The `g4s_schemas.py` module provides **StructType schemas** for all Go4Schools API endpoints. These schemas:

- ✅ **Validate data at ingestion** - Catch API changes or data issues early
- ✅ **Improve performance** - Eliminate schema inference overhead
- ✅ **Document contracts** - Serve as explicit API documentation
- ✅ **Enable evolution** - Track schema changes over time

## Schema Architecture

All schemas map 1:1 to the original C# DTO classes from the .NET application.

### Field Naming Convention
- **API fields**: snake_case (e.g., `first_name`, `student_id`)
- **Metadata fields**: Prefixed with `_` (e.g., `_academy_code`, `_ingested_at`)

### Metadata Fields (Raw Layer)

Every raw table includes these metadata fields:

```python
_academy_code      # STRING  - Academy identifier
_academic_year     # STRING  - Academic year (e.g., "2024")
_endpoint          # STRING  - Source endpoint name
_ingested_at       # STRING  - ISO timestamp of ingestion
```

## Using Schemas

### In Raw Layer Ingestion

```python
from g4s_schemas import get_schema_for_endpoint, add_metadata_to_schema

# Get schema for an endpoint
base_schema = get_schema_for_endpoint("student_details")

# Add metadata fields for raw storage
full_schema = add_metadata_to_schema(base_schema)

# Create DataFrame with validation
json_rdd = spark.sparkContext.parallelize([json.dumps(record) for record in data])
df = spark.read.schema(full_schema).json(json_rdd)
```

### In Base Layer Transformations

```python
from g4s_schemas import STUDENT_DETAILS_SCHEMA

# Use schema directly
df = spark.read.schema(STUDENT_DETAILS_SCHEMA).json(raw_data)

# Or reference specific fields
from pyspark.sql.types import StructField

student_id_field = next(f for f in STUDENT_DETAILS_SCHEMA.fields if f.name == "id")
```

## Schema Catalog

### STUDENTS Domain

| Schema Name | Endpoint | Key Fields |
|------------|----------|-----------|
| `STUDENT_DETAILS_SCHEMA` | `student_details` | id, legal_first_name, legal_last_name, date_of_birth, sex |
| `EDUCATION_DETAILS_SCHEMA` | `education_details` | student_id, mis_id, upn, year_group, registration_group |
| `ATTRIBUTE_VALUE_SCHEMA` | `*_attributes` | student_id, attribute_id, value_id, value |

### TEACHING Domain

| Schema Name | Endpoint | Key Fields |
|------------|----------|-----------|
| `DEPARTMENT_SCHEMA` | `departments` | id, name, code |
| `SUBJECT_SCHEMA` | `subjects` | id, name, code, department_id |
| `GROUP_SCHEMA` | `groups` | id, name, code, subject_id |
| `GROUP_STUDENTS_SCHEMA` | `group_students` | group_id, student_ids (array) |
| `TEACHER_SCHEMA` | `teachers` | id, staff_code, first_name, last_name |

### ASSESSMENT Domain

| Schema Name | Endpoint | Key Fields |
|------------|----------|-----------|
| `MARKBOOK_SCHEMA` | `markbooks` | id, name, group_id, staff_owner_id |
| `MARKSHEET_GRADE_SCHEMA` | `marksheet_grades` | id, grades (nested array) |
| `MARKSLOT_MARK_SCHEMA` | `markslot_marks` | id, marks (nested array) |

### ATTAINMENT Domain

| Schema Name | Endpoint | Key Fields |
|------------|----------|-----------|
| `PRIOR_ATTAINMENT_SCHEMA` | `prior_attainment` | student_id, dataset_id, subject_id, grade_id, points |
| `GRADE_NAME_SCHEMA` | `grade_names` | id, name, code |
| `GRADE_SCHEMA` | `grades` | id, name, points, grade_name_id |
| `EXAM_RESULT_SCHEMA` | `exam_results` | student_id, qualification_id, subject_id, grade_id, year |

### ATTENDANCE Domain

| Schema Name | Endpoint | Key Fields |
|------------|----------|-----------|
| `ATTENDANCE_CODE_SCHEMA` | `attendance_codes` | id, code, description, category, authorised, present |
| `STUDENT_LESSON_MARK_SCHEMA` | `student_lesson_marks` | student_id, class_id, date, period_id, attendance_code_id |
| `STUDENT_SESSION_MARK_SCHEMA` | `student_session_marks` | student_id, date, session, attendance_code_id |
| `STUDENT_SESSION_SUMMARY_SCHEMA` | `student_session_summaries` | student_id, possible_sessions, present, late |

### TIMETABLE Domain

| Schema Name | Endpoint | Key Fields |
|------------|----------|-----------|
| `CALENDAR_SCHEMA` | `calendar` | date, week_number, week_letter, term, academic_year |
| `PERIOD_SCHEMA` | `periods` | id, name, start_time, end_time |
| `TIMETABLE_CLASS_SCHEMA` | `timetable_classes` | id, name, group_id, teacher_id, room, day, period_id |

### BEHAVIOUR Domain

| Schema Name | Endpoint | Key Fields |
|------------|----------|-----------|
| `BEHAVIOUR_CLASSIFICATION_SCHEMA` | `behaviour_classifications` | id, name, description |
| `BEHAVIOUR_EVENT_TYPE_SCHEMA` | `behaviour_event_types` | id, name, classification_id, points, active |
| `BEHAVIOUR_EVENT_SCHEMA` | `behaviour_events` | id, student_id, event_type_id, date, period_id, points |

### USERS Domain

| Schema Name | Endpoint | Key Fields |
|------------|----------|-----------|
| `STAFF_SCHEMA` | `staff` | id, staff_code, first_name, last_name, email |

## Schema Evolution

When the Go4Schools API changes, update schemas in `g4s_schemas.py`:

### Adding a New Field

```python
STUDENT_DETAILS_SCHEMA = StructType([
    # ... existing fields ...
    StructField("new_field_name", StringType(), True),  # nullable=True for backward compatibility
])
```

### Making a Field Nullable

```python
# Change nullable from False to True
StructField("field_name", StringType(), True)  # Was: False
```

### Changing Field Type

```python
# This is a breaking change - requires data migration
StructField("year_group", StringType(), True)  # Was: IntegerType()

# Better approach: Add new field, migrate, then remove old field
StructField("year_group", IntegerType(), True),      # Keep for compatibility
StructField("year_group_str", StringType(), True),   # New field
```

## Nested Schemas

Some endpoints return nested structures (e.g., marksheet grades):

```python
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
```

Access nested data using:

```python
# Explode nested array
df.select("id", explode("grades").alias("grade"))

# Access nested struct fields
df.select("id", col("grades.student_id"), col("grades.grade_name"))
```

## Type Mapping: C# to PySpark

| C# Type | PySpark Type | Notes |
|---------|--------------|-------|
| `int` | `IntegerType()` | 32-bit signed integer |
| `long` | `LongType()` | 64-bit signed integer |
| `string` | `StringType()` | UTF-8 encoded string |
| `bool` | `BooleanType()` | true/false |
| `DateTime` | `TimestampType()` | Microsecond precision |
| `decimal` | `DecimalType()` | Fixed precision |
| `double` | `DoubleType()` | Floating point |
| `List<T>` | `ArrayType(T)` | Array of type T |
| `Dictionary<K,V>` | `MapType(K,V)` | Key-value pairs |
| `MyClass` | `StructType([...])` | Nested object |

## Validation Examples

### Catch Missing Required Fields

```python
# Schema with non-nullable field
schema = StructType([
    StructField("id", IntegerType(), False),  # Required
    StructField("name", StringType(), True),   # Optional
])

# This will fail if 'id' is missing or null
df = spark.read.schema(schema).json(data)
```

### Enforce Data Types

```python
# API returns string "123" instead of integer 123
data = [{"id": "123"}]  # Wrong type

schema = StructType([
    StructField("id", IntegerType(), False)
])

# This will cast to integer or fail
df = spark.read.schema(schema).json(data)
```

## Best Practices

1. **Always use schemas** - Don't rely on schema inference for production
2. **Mark IDs as non-nullable** - Primary/foreign keys should be `nullable=False`
3. **Use nullable=True for new fields** - Allows backward compatibility
4. **Document nested structures** - Add comments for complex schemas
5. **Version your schemas** - Consider schema versioning for major changes
6. **Test schema changes** - Validate against sample API responses before deployment

## Troubleshooting

### Schema Mismatch Errors

```
org.apache.spark.sql.AnalysisException: Cannot safely cast 'field_name': StringType to IntegerType
```

**Solution**: Check API response format - field type may have changed

### Missing Field Errors

```
java.lang.IllegalArgumentException: Field "field_name" does not exist
```

**Solution**: Field may be optional or removed from API - add to schema with `nullable=True`

### Nested Field Access Issues

```python
# Wrong
df.select("grades.student_id")

# Correct
df.select(col("grades.student_id"))
# or
df.select("grades.*")
```

## See Also

- [Raw Layer Ingestion Notebook](../01_RawLayer_Ingestion.ipynb) - Uses schemas for validation
- [Delta Manager Module](delta_manager.py) - Schema-aware write operations
- [PySpark StructType Documentation](https://spark.apache.org/docs/latest/api/python/reference/pyspark.sql/api/pyspark.sql.types.StructType.html)
