# G4S API Sync - Microsoft Fabric Migration

This repository contains the migrated PySpark notebooks and utilities for syncing data from the Go4Schools (G4S) API to Microsoft Fabric Delta tables.

## 🏗️ Architecture

The solution implements a **medallion architecture** with two layers:

### Raw Layer (Bronze)
- Stores unmodified JSON responses from the G4S API
- Partitioned by `academy_code` and `academic_year`
- Includes audit columns: `_ingested_at`, `_source`, `_endpoint`
- Tables: `raw_g4s_*`

### Base Layer (Silver)
- Structured, cleaned data with proper schemas
- Matches the original SQL Server table structure
- Partitioned by `Academy` and `DataSet`
- Tables: `base_*`

## 📁 Project Structure

```
fabric_notebooks/
├── utils/
│   ├── g4s_api_client.py         # API client with pagination and error handling
│   ├── keyvault_client.py        # Azure Key Vault integration
│   └── delta_manager.py          # Delta table operations
├── sql/
│   ├── 01_Create_AcademySecurity_Table.sql
│   └── 02_Create_SyncResults_Table.sql
├── 00_Orchestration.ipynb        # Main orchestration notebook
├── 01_RawLayer_Ingestion.ipynb  # Raw layer ingestion
├── 02_BaseLayer_Students.ipynb  # Student data transformation
└── 03_BaseLayer_Teaching_Assessment.ipynb  # Teaching/Assessment transformation
```

## 🔧 Prerequisites

1. **Microsoft Fabric Workspace**
   - Lakehouse created and attached to notebooks
   - Appropriate permissions (Contributor or Admin)

2. **Azure Key Vault**
   - Key Vault created with API keys stored as secrets
   - Fabric workspace service principal granted access (Get Secret permission)

3. **SQL Metadata Tables**
   - `sec.AcademySecurity` table created (use SQL scripts in `sql/` folder)
   - `sec.SyncResults` table created for tracking

4. **Python Packages**
   Required packages (usually pre-installed in Fabric):
   - `pyspark`
   - `delta-spark`
   - `requests`
   - `azure-identity`
   - `azure-keyvault-secrets`

## 🚀 Setup Instructions

### Step 1: Create Metadata Tables

Run the SQL scripts to create metadata tables:

```sql
-- In your Fabric SQL endpoint or Azure SQL Database
-- Run these scripts in order:
sql/01_Create_AcademySecurity_Table.sql
sql/02_Create_SyncResults_Table.sql
```

### Step 2: Configure Academy Metadata

Insert academy configurations into `AcademySecurity` table:

```sql
INSERT INTO sec.AcademySecurity 
    (AcademyCode, Name, CurrentAcademicYear, KeyVaultSecretName, Active, 
     LowestYear, HighestYear, GetLessonAttendance, GetSessionAttendance, 
     AttendanceFrom, AttendanceTo, GetBehaviour, BehaviourFrom, BehaviourTo)
VALUES 
    ('ABC', 'Example Academy', '2324', 'g4s-api-key-abc', 1, 
     7, 13, 1, 1, 
     '2023-09-01', '2024-07-31', 1, '2023-09-01', '2024-07-31');
```

### Step 3: Store API Keys in Azure Key Vault

Store each academy's API key as a secret in Azure Key Vault:

```bash
# Using Azure CLI
az keyvault secret set \
  --vault-name "your-keyvault" \
  --name "g4s-api-key-abc" \
  --value "your-api-key-here"
```

### Step 4: Grant Fabric Access to Key Vault

Configure Key Vault access policy for Fabric workspace:

```bash
# Get the Fabric workspace managed identity from Workspace Settings → Identity
# Grant it "Get" permission on secrets
az keyvault set-policy \
  --name "your-keyvault" \
  --object-id "<fabric-workspace-managed-identity-id>" \
  --secret-permissions get
```

**Note**: Fabric uses `notebookutils.credentials.getSecret()` which automatically handles authentication using the workspace managed identity.

### Step 5: Upload Utilities to Lakehouse

1. In your Fabric workspace, open the Lakehouse
2. Navigate to Files → Create folder: `notebooks/utils`
3. Upload the Python utility files:
   - `g4s_api_client.py` - API client with pagination
   - `keyvault_client.py` - Key Vault integration
   - `delta_manager.py` - Delta table operations
   - `g4s_schemas.py` - **Schema definitions for data validation**

### Step 6: Import Notebooks

1. In Fabric workspace, import the notebooks:
   - `00_Orchestration.ipynb`
   - `01_RawLayer_Ingestion.ipynb`
   - `02_BaseLayer_Students.ipynb`
   - `03_BaseLayer_Teaching_Assessment.ipynb`

2. Attach the Lakehouse to each notebook

### Step 7: Configure Notebook Parameters

Update configuration in `01_RawLayer_Ingestion.ipynb`:

```python
KEY_VAULT_URL = "https://your-keyvault.vault.azure.net/"
SQL_ENDPOINT = "your-fabric-sql-endpoint"
DATABASE_NAME = "your-database"
```

## 📊 Usage

### Full Sync

Run the orchestration notebook to sync all data:

```python
# In 00_Orchestration.ipynb
sync_scope = "FULL"
skip_raw = False
skip_base = False
```

### Partial Sync

Sync specific domains:

```python
# Students only
sync_scope = "STUDENTS"

# Teaching and Assessment only
sync_scope = "TEACHING"

# Options: STUDENTS, TEACHING, ASSESSMENT, ATTAINMENT, 
#          ATTENDANCE, TIMETABLE, BEHAVIOUR, USERS
```

### Raw Layer Only

Ingest data without transformation:

```python
sync_scope = "FULL"
skip_raw = False
skip_base = True  # Skip transformation
```

### Transform Existing Raw Data

Transform without re-ingesting:

```python
sync_scope = "FULL"
skip_raw = True   # Skip ingestion
skip_base = False
```

## 🗂️ Data Tables

### Metadata Tables
- `sec.AcademySecurity` - Academy configuration and API settings (SQL Server/Azure SQL)
- `sec.SyncResults` - Sync execution tracking and logging (SQL Server/Azure SQL)

**Note**: Metadata tables use T-SQL (SQL Server), while data tables use Spark SQL (Delta Lake). Be aware of syntax differences when querying.

### Raw Layer Tables (Bronze)
- `raw_g4s_student_details`
- `raw_g4s_education_details`
- `raw_g4s_general_attributes`
- `raw_g4s_demographic_attributes`
- `raw_g4s_send_attributes`
- `raw_g4s_sensitive_attributes`
- `raw_g4s_departments`
- `raw_g4s_subjects`
- `raw_g4s_groups`
- `raw_g4s_group_students`
- `raw_g4s_teachers`
- `raw_g4s_markbooks`
- `raw_g4s_marksheet_grades`
- `raw_g4s_markslot_marks`

### Base Layer Tables (Silver)
- `base_students`
- `base_education_details`
- `base_student_attributes`
- `base_departments`
- `base_subjects`
- `base_groups`
- `base_group_students`
- `base_teachers`
- `base_markbooks`
- `base_marksheet_grades`
- `base_markslot_marks`

## 🔄 Migration from C# .NET

### Key Changes

1. **Authentication**
   - **Before**: API keys stored directly in `AcademySecurity.APIKey`
   - **After**: Secret names stored in `AcademySecurity.KeyVaultSecretName`, actual keys in Azure Key Vault

2. **Data Storage**
   - **Before**: Direct SQL Server bulk insert
   - **After**: Two-layer approach (Raw → Base) using Delta tables

3. **Schema Validation**
   - **Before**: Strongly-typed C# entities (DTOs) provide compile-time validation
   - **After**: PySpark StructType schemas provide runtime validation
   - **Benefit**: Catches API changes and data quality issues at ingestion time
   - **See**: [SCHEMA_REFERENCE.md](SCHEMA_REFERENCE.md) for complete schema catalog

4. **Error Handling**
   - **Before**: Try-catch with immediate SQL logging
   - **After**: Same pattern preserved, logged to `sec.SyncResults`

5. **Pagination**
   - **Before**: RestSharp with cursor-based pagination
   - **After**: Python `requests` library with same pagination logic

6. **Partitioning**
   - **Before**: No partitioning (single SQL tables)
   - **After**: Partitioned Delta tables by Academy and DataSet

### Logic Preserved

The transformation logic closely mirrors the original C# implementation:
- Same composite key generation (`AcademyCode + DataSet + "-" + Id`)
- Same field mappings and data types
- Same delete-before-insert pattern (now using partition deletion)
- Same sync result tracking

## 📅 Scheduling

### Using Fabric Pipelines

Create a pipeline to schedule the orchestration notebook:

1. Create new Data Pipeline
2. Add "Notebook" activity
3. Select `00_Orchestration` notebook
4. Configure parameters
5. Set schedule trigger (e.g., daily at 2 AM)

### Using Fabric Data Workflows

Alternatively, use Fabric's Data Workflows for more complex orchestration.

## 🐛 Troubleshooting

### Key Vault Access Issues

```python
# Error: Unable to retrieve secret
# Solution: Verify workspace managed identity has "Get" permission on secrets
```

Check Key Vault access policies and ensure Fabric workspace identity has access.

### Schema Validation Errors

```python
# Error: Cannot safely cast 'field_name': StringType to IntegerType
# Solution: API response format may have changed - check actual data
```

Common causes:
- API returns string where integer expected
- Field is null when marked as non-nullable in schema
- Nested structure changed

**Fix**: Update schema in `g4s_schemas.py` or set `nullable=True` for affected field.

See [SCHEMA_REFERENCE.md](SCHEMA_REFERENCE.md) for troubleshooting guide.

### Table Not Found Errors

```python
# Error: Table 'raw_g4s_students' not found
# Solution: Run raw layer ingestion first
```

Ensure raw layer ingestion completes before running transformations.

### API Rate Limits

The client includes automatic retry logic with exponential backoff. If issues persist:
- Check API rate limits with G4S support
- Adjust retry settings in `g4s_api_client.py`

### Memory Issues with Large Datasets

If processing fails due to memory:
- Reduce parallelism: `.repartition(10)` before writes
- Process academies sequentially rather than in parallel
- Increase cluster size in Fabric workspace settings

## 📈 Performance Optimization

### Delta Table Optimization

Run regularly to maintain performance:

```python
# Optimize tables
OPTIMIZE base_students ZORDER BY (Academy, DataSet)

# Vacuum old files (7 day retention)
VACUUM base_students RETAIN 168 HOURS
```

### Caching

For repeated reads of raw data:

```python
raw_df = spark.table("raw_g4s_students").cache()
```

## 🔐 Security Best Practices

1. **Never commit API keys** to source control
2. **Use Key Vault** for all sensitive configuration
3. **Limit Key Vault access** to minimum required permissions
4. **Enable audit logging** on Key Vault access
5. **Rotate API keys** regularly
6. **Use Fabric workspace roles** to control notebook access

## 📞 Support

For issues specific to:
- **G4S API**: Contact Go4Schools support
- **Microsoft Fabric**: Reference [Microsoft Fabric documentation](https://learn.microsoft.com/fabric/)
- **Schema Validation**: See [SCHEMA_REFERENCE.md](SCHEMA_REFERENCE.md)
- **This implementation**: Review notebooks and check `sec.SyncResults` for errors

## 📚 Additional Documentation

- **[SCHEMA_REFERENCE.md](SCHEMA_REFERENCE.md)** - Complete schema catalog, type mappings, and validation guide
- **[MIGRATION_GUIDE.md](MIGRATION_GUIDE.md)** - Detailed migration walkthrough
- **[MIGRATION_CHECKLIST.md](MIGRATION_CHECKLIST.md)** - Step-by-step deployment checklist
- **[QUICK_REFERENCE.md](QUICK_REFERENCE.md)** - Quick commands and troubleshooting

## 📝 License

This project maintains the same license as the original C# implementation.

## 🔄 Version History

- **v2.0** - PySpark/Fabric migration with medallion architecture
- **v1.0** - Original C# .NET 9 console application

---

**Original C# Implementation**: See `G4SApiSync/` and `G4SApiSync.Client/` folders for reference
