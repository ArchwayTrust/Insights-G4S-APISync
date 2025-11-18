# Migration Guide: C# .NET to PySpark/Fabric

This guide helps you migrate from the on-premises C# .NET 9 console application to Microsoft Fabric PySpark notebooks.

## Overview of Changes

| Aspect | C# .NET (Before) | PySpark/Fabric (After) |
|--------|------------------|------------------------|
| Runtime | Console app on Windows Server | Notebooks in Microsoft Fabric |
| Language | C# | Python (PySpark) |
| Data Storage | SQL Server (single tables) | Delta Lake (partitioned) |
| Architecture | Single-tier (API → SQL) | Two-tier (API → Raw → Base) |
| Secrets | Database column | Azure Key Vault |
| Scheduling | Windows Task Scheduler | Fabric Pipelines |
| Scalability | Single-threaded | Distributed (Spark) |

## Migration Steps

### 1. Export Current Configuration

From your SQL Server database:

```sql
-- Export academy configurations
SELECT 
    AcademyCode,
    Name,
    CurrentAcademicYear,
    APIKey,  -- Will become KeyVaultSecretName
    Active,
    LowestYear,
    HighestYear,
    GetLessonAttendance,
    GetSessionAttendance,
    AttendanceFrom,
    AttendanceTo,
    GetBehaviour,
    BehaviourFrom,
    BehaviourTo
FROM sec.AcademySecurity
WHERE Active = 1;
```

### 2. Set Up Azure Key Vault

```bash
# Create Key Vault (if not exists)
az keyvault create \
  --name "archway-g4s-keyvault" \
  --resource-group "your-rg" \
  --location "uksouth"

# Store each academy's API key
# Replace ABC with academy code
az keyvault secret set \
  --vault-name "archway-g4s-keyvault" \
  --name "g4s-api-key-ABC" \
  --value "actual-api-key-from-database"
```

### 3. Create Fabric Workspace

1. Navigate to Microsoft Fabric portal
2. Create new workspace: "G4S API Sync"
3. Create Lakehouse: "g4s_data"
4. Create SQL endpoint for metadata tables

### 4. Migrate Metadata Tables

Run the SQL scripts in Fabric SQL endpoint or Azure SQL:

```sql
-- Run in order:
-- 1. Create AcademySecurity table (modified schema)
SOURCE: fabric_notebooks/sql/01_Create_AcademySecurity_Table.sql

-- 2. Create SyncResults table
SOURCE: fabric_notebooks/sql/02_Create_SyncResults_Table.sql
```

Then insert configurations (using Key Vault secret names):

```sql
INSERT INTO sec.AcademySecurity 
    (AcademyCode, Name, CurrentAcademicYear, KeyVaultSecretName, ...)
VALUES 
    ('ABC', 'Academy Name', '2324', 'g4s-api-key-ABC', ...);
```

### 5. Upload Utility Modules

1. In Fabric Lakehouse, create folder: `Files/notebooks/utils`
2. Upload these files:
   - `fabric_notebooks/utils/g4s_api_client.py`
   - `fabric_notebooks/utils/keyvault_client.py`
   - `fabric_notebooks/utils/delta_manager.py`

### 6. Import Notebooks

Import all notebooks into Fabric workspace:
- `00_Orchestration.ipynb`
- `01_RawLayer_Ingestion.ipynb`
- `02_BaseLayer_Students.ipynb`
- `03_BaseLayer_Teaching_Assessment.ipynb`

For each notebook:
1. Click "Import" → "Upload notebook"
2. Select the `.ipynb` file
3. Attach the `g4s_data` lakehouse

### 7. Configure Notebooks

Update `01_RawLayer_Ingestion.ipynb` parameters:

```python
KEY_VAULT_URL = "https://archway-g4s-keyvault.vault.azure.net/"
SQL_ENDPOINT = "your-fabric-sql-endpoint.database.windows.net"
DATABASE_NAME = "your-database"
```

### 8. Grant Fabric Access to Key Vault

```bash
# Get Fabric workspace managed identity
# From Fabric workspace settings → Identity

# Grant access
az keyvault set-policy \
  --name "archway-g4s-keyvault" \
  --object-id "<workspace-identity-object-id>" \
  --secret-permissions get list
```

### 9. Test Run

Run a test sync for a single academy:

1. Temporarily update `sec.AcademySecurity` to have only one active academy
2. Run `00_Orchestration.ipynb` with `sync_scope = "STUDENTS"`
3. Verify data in `raw_g4s_student_details` and `base_students` tables
4. Check `sec.SyncResults` for success/failure

### 10. Schedule Production Runs

Create a Fabric Pipeline:

1. New Data Pipeline: "G4S Daily Sync"
2. Add Notebook activity → Select `00_Orchestration`
3. Set parameters:
   ```json
   {
     "sync_scope": "FULL",
     "skip_raw": false,
     "skip_base": false
   }
   ```
4. Add schedule trigger: Daily at 2:00 AM

## Code Mapping Reference

### API Request Logic

**C# (APIRequest.cs)**
```csharp
var request = new RestRequest(fullResource, Method.Get);
request.AddHeader("Authorization", "Bearer " + pBearer);
request.AddParameter("academicYear", pAcYear);
RestResponse response = pClient.Get(request);
```

**Python (g4s_api_client.py)**
```python
response = requests.get(
    url,
    headers={"Authorization": f"Bearer {api_key}"},
    params={"academicYear": academic_year},
    timeout=timeout
)
```

### Pagination Logic

**C# (APIRequest.cs)**
```csharp
do {
    var result = ReturnedJSON(cursor);
    listToReturn.AddRange(JsonConvert.DeserializeObject<EndPoint>(result).DTOs);
    cursor = JsonConvert.DeserializeObject<EndPoint>(result).Cursor;
} while (JsonConvert.DeserializeObject<EndPoint>(result).HasMore);
```

**Python (g4s_api_client.py)**
```python
while has_more:
    response = self._make_request(endpoint, params, cursor)
    all_data.extend(response[data_key])
    has_more = response.get('has_more', False)
    cursor = response.get('cursor')
```

### Data Transformation

**C# (GETStudentDetails.cs)**
```csharp
row["StudentId"] = AcademyCode + AcYear + "-" + studentDTO.Id.ToString();
row["DataSet"] = AcYear;
row["Academy"] = AcademyCode;
row["DateOfBirth"] = DateTime.ParseExact(studentDTO.DateOfBirth, ...);
```

**Python (02_BaseLayer_Students.ipynb)**
```python
base_students = raw_students.select(
    concat(col("_academy_code"), col("_academic_year"), lit("-"), col("id")).alias("StudentId"),
    col("_academic_year").alias("DataSet"),
    col("_academy_code").alias("Academy"),
    to_timestamp(col("date_of_birth"), "yyyy-MM-dd'T'HH:mm:ss'Z'").alias("DateOfBirth")
)
```

### Bulk Insert/Update

**C# (GETStudentDetails.cs)**
```csharp
// Delete existing
_context.Students.RemoveRange(currentStudents);
await _context.SaveChangesAsync();

// Bulk insert
using (var sqlBulk = new SqlBulkCopy(_connectionString))
{
    sqlBulk.DestinationTableName = "g4s.Students";
    sqlBulk.WriteToServer(dtStudents);
}
```

**Python (02_BaseLayer_Students.ipynb)**
```python
# Overwrite partition
base_students.write \
    .format("delta") \
    .mode("overwrite") \
    .partitionBy("Academy", "DataSet") \
    .saveAsTable("base_students")
```

## Data Schema Comparison

### Students Table

| C# SQL Schema | Fabric Delta Schema | Notes |
|---------------|---------------------|-------|
| `StudentId` (PK) | `StudentId` | Same composite key format |
| `DataSet` | `DataSet` | Same |
| `Academy` | `Academy` | Same |
| `G4SStuId` | `G4SStuId` | Same |
| `DateOfBirth` (DateTime) | `DateOfBirth` (Timestamp) | Compatible |
| N/A | `IngestedAt` | New: Audit column |
| N/A | `TransformedAt` | New: Audit column |

### Key Changes
- **Partitioning**: Delta tables partitioned by `Academy` and `DataSet` for performance
- **Audit Columns**: Added `IngestedAt`, `TransformedAt` for lineage
- **Raw Layer**: New intermediate layer preserving original JSON

## Performance Considerations

### C# Console App
- Single-threaded execution
- Sequential API calls per academy
- Direct SQL bulk insert
- Typical runtime: 30-60 minutes for full sync

### PySpark Notebooks
- Distributed processing
- Parallel API calls possible (currently sequential for safety)
- Delta Lake with Z-ordering
- Expected runtime: 20-40 minutes for full sync (with optimization)

## Rollback Plan

If issues occur, you can continue running the C# application:

1. Keep existing C# application running
2. Test Fabric notebooks in parallel with non-production academies
3. Compare data quality between both systems
4. Gradually migrate academies once confident

## Validation Queries

Compare record counts between old and new systems:

```sql
-- C# SQL Server
SELECT 
    Academy,
    DataSet,
    COUNT(*) as StudentCount
FROM g4s.Students
GROUP BY Academy, DataSet
ORDER BY Academy, DataSet;

-- Fabric Delta
SELECT 
    Academy,
    DataSet,
    COUNT(*) as StudentCount
FROM base_students
GROUP BY Academy, DataSet
ORDER BY Academy, DataSet;
```

## Common Issues and Solutions

### Issue: Key Vault Access Denied
**Solution**: Verify workspace managed identity has "Get" permission on Key Vault secrets

### Issue: Table Not Found
**Solution**: Ensure lakehouse is attached and raw layer ingestion completed

### Issue: Slow Performance
**Solution**: 
- Check Spark cluster size
- Optimize Delta tables with Z-ordering
- Consider partitioning strategy

### Issue: API Rate Limiting
**Solution**: 
- Implement delays between academy processing
- Check G4S API rate limits
- Contact G4S support if needed

## Next Steps After Migration

1. **Monitor Performance**: Track sync duration and optimize as needed
2. **Data Quality**: Set up automated data quality checks
3. **Alerting**: Configure alerts for failed syncs
4. **Documentation**: Update team documentation with new processes
5. **Decommission**: Once stable, decommission C# application

## Support Contacts

- **Fabric Issues**: Microsoft Support
- **G4S API**: Go4Schools Support
- **Key Vault**: Azure Support
- **Migration Questions**: Check this documentation first

---

**Remember**: Test thoroughly with non-production academies before full migration!
