# G4S API Sync - Migration Checklist

Use this checklist to track your migration progress from C# .NET to PySpark/Fabric.

## Pre-Migration

- [ ] Review `SUMMARY.md` for overview
- [ ] Read `MIGRATION_GUIDE.md` in detail
- [ ] Identify test academy for pilot
- [ ] Schedule migration window
- [ ] Backup current SQL Server database
- [ ] Export current `sec.AcademySecurity` configurations

## Infrastructure Setup

### Azure Key Vault
- [ ] Create Azure Key Vault (or use existing)
- [ ] Note Key Vault URL: `____________________________`
- [ ] Store API keys as secrets:
  - [ ] Academy 1: Secret name: `____________________________`
  - [ ] Academy 2: Secret name: `____________________________`
  - [ ] Academy 3: Secret name: `____________________________`
  - [ ] (Add more as needed)
- [ ] Test secret retrieval with Azure CLI

### Microsoft Fabric
- [ ] Create Fabric workspace: Name: `____________________________`
- [ ] Create lakehouse: Name: `____________________________`
- [ ] Note SQL endpoint: `____________________________`
- [ ] Verify workspace capacity and region

### Metadata Database
- [ ] Decide: Use Fabric SQL endpoint or separate Azure SQL Database?
- [ ] Run `01_Create_AcademySecurity_Table.sql`
- [ ] Run `02_Create_SyncResults_Table.sql`
- [ ] Verify tables created successfully
- [ ] Insert academy configurations with Key Vault secret names
- [ ] Test query: `SELECT * FROM sec.AcademySecurity WHERE Active = 1`

## Security Configuration

- [ ] Get Fabric workspace managed identity Object ID
- [ ] Grant Key Vault "Get" permission to Fabric identity
- [ ] Test Key Vault access from Fabric notebook:
  ```python
  from azure.identity import DefaultAzureCredential
  from azure.keyvault.secrets import SecretClient
  client = SecretClient(vault_url="https://...", credential=DefaultAzureCredential())
  secret = client.get_secret("test-secret-name")
  ```

## Code Deployment

### Upload Utility Files
- [ ] In lakehouse, create folder: `Files/notebooks/utils`
- [ ] Upload `g4s_api_client.py`
- [ ] Upload `keyvault_client.py`
- [ ] Upload `delta_manager.py`
- [ ] Verify file paths are correct

### Import Notebooks
- [ ] Import `00_Orchestration.ipynb`
- [ ] Import `01_RawLayer_Ingestion.ipynb`
- [ ] Import `02_BaseLayer_Students.ipynb`
- [ ] Import `03_BaseLayer_Teaching_Assessment.ipynb`
- [ ] Attach lakehouse to all notebooks

### Configure Notebooks
- [ ] Update `01_RawLayer_Ingestion.ipynb`:
  - [ ] Set `KEY_VAULT_URL`
  - [ ] Set `SQL_ENDPOINT`
  - [ ] Set `DATABASE_NAME`
- [ ] Verify Python module imports work

## Testing Phase

### Pilot Test (Single Academy)
- [ ] Disable all academies in `sec.AcademySecurity` except test academy
- [ ] Run `00_Orchestration.ipynb` with `sync_scope = "STUDENTS"`
- [ ] Verify raw tables created: `raw_g4s_student_details`
- [ ] Verify base tables created: `base_students`
- [ ] Check row counts match expectations
- [ ] Review `sec.SyncResults` for any errors

### Validation Queries
- [ ] Run validation queries comparing C# output to PySpark output:
  ```sql
  -- Student counts
  SELECT Academy, DataSet, COUNT(*) as Count
  FROM base_students
  GROUP BY Academy, DataSet
  ORDER BY Academy, DataSet;
  ```
- [ ] Verify data types are correct
- [ ] Spot-check sample records for accuracy
- [ ] Confirm date formats are preserved

### Full Domain Test
- [ ] Run with `sync_scope = "TEACHING"`
- [ ] Run with `sync_scope = "ASSESSMENT"`
- [ ] Verify all endpoint data ingested correctly
- [ ] Check for any failed syncs in `sec.SyncResults`

### Performance Test
- [ ] Note sync duration: `____________________________`
- [ ] Compare to C# sync duration: `____________________________`
- [ ] Check Spark cluster utilization
- [ ] Optimize if needed (Z-ordering, partitioning)

## Production Deployment

### Enable All Academies
- [ ] Re-enable all academies in `sec.AcademySecurity`
- [ ] Run full sync: `sync_scope = "FULL"`
- [ ] Monitor for any issues
- [ ] Verify all academies synced successfully

### Create Pipeline
- [ ] Create new Data Pipeline: "G4S Daily Sync"
- [ ] Add Notebook activity → `00_Orchestration`
- [ ] Set parameters:
  ```json
  {
    "sync_scope": "FULL",
    "skip_raw": false,
    "skip_base": false
  }
  ```
- [ ] Configure schedule (e.g., Daily at 2:00 AM)
- [ ] Set up failure notifications/alerts
- [ ] Test pipeline execution manually

### Monitoring Setup
- [ ] Create monitoring query for failed syncs:
  ```sql
  SELECT * FROM sec.SyncResults 
  WHERE Result = 0 
  AND LoggedAt >= DATEADD(day, -7, GETUTCDATE())
  ORDER BY LoggedAt DESC;
  ```
- [ ] Set up email alerts for failures (if available)
- [ ] Document who to contact for issues

## Parallel Running (Optional)

If running both systems in parallel initially:
- [ ] Schedule Fabric sync to run after C# sync
- [ ] Daily comparison of record counts
- [ ] Weekly data quality checks
- [ ] Document any discrepancies
- [ ] Duration: `____________________________` (e.g., 2 weeks)

## C# Decommissioning

Once confident in Fabric implementation:
- [ ] Disable C# scheduled task
- [ ] Archive C# application code
- [ ] Document final C# sync date: `____________________________`
- [ ] Keep C# code available for 90 days as rollback option

## Documentation Updates

- [ ] Update team documentation with new process
- [ ] Document Key Vault secret naming convention
- [ ] Update runbook with Fabric-specific troubleshooting
- [ ] Train team members on new system
- [ ] Update incident response procedures

## Maintenance Tasks

Set up recurring tasks:
- [ ] Weekly: Review `sec.SyncResults` for errors
- [ ] Monthly: Optimize Delta tables
  ```sql
  OPTIMIZE base_students ZORDER BY (Academy, DataSet);
  ```
- [ ] Monthly: Vacuum old files
  ```sql
  VACUUM base_students RETAIN 168 HOURS;
  ```
- [ ] Quarterly: Review and rotate API keys
- [ ] Annually: Review partitioning strategy

## Post-Migration Review

After 30 days:
- [ ] Review sync reliability (success rate)
- [ ] Compare performance to C# implementation
- [ ] Gather feedback from data consumers
- [ ] Identify optimization opportunities
- [ ] Document lessons learned

## Rollback Plan (If Needed)

If critical issues arise:
- [ ] Re-enable C# scheduled task immediately
- [ ] Document issues encountered
- [ ] Fix issues in Fabric notebooks
- [ ] Re-test in isolated environment
- [ ] Attempt migration again when ready

## Sign-Off

- [ ] Technical lead approval: _________________ Date: _______
- [ ] Data engineering approval: _________________ Date: _______
- [ ] Business stakeholder approval: _________________ Date: _______

---

## Notes and Observations

Use this space to track issues, decisions, and important notes during migration:

```
Date       | Note
-----------|----------------------------------------------------------






```

## Key Contacts

| Role | Name | Contact |
|------|------|---------|
| Migration Lead | _________________ | _________________ |
| Fabric Admin | _________________ | _________________ |
| Azure Admin | _________________ | _________________ |
| G4S API Support | _________________ | _________________ |

---

**Migration Status**: ⬜ Not Started | 🟡 In Progress | ✅ Complete

Last Updated: _________________
