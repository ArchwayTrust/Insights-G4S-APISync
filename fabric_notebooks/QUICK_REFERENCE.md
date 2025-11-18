# G4S API Sync - Quick Reference Card

## 📞 Emergency Contacts
- **Technical Lead**: _______________
- **Fabric Support**: Microsoft Support Portal
- **G4S API Support**: Go4Schools Support

## 🚀 Running a Sync

### Full Sync (All Data)
1. Open `00_Orchestration` notebook in Fabric
2. Ensure parameters are set:
   ```python
   sync_scope = "FULL"
   ```
3. Click "Run All"
4. Monitor progress (approx. 30-60 minutes)

### Partial Sync (Specific Domain)
```python
sync_scope = "STUDENTS"    # Students only
sync_scope = "TEACHING"    # Teaching data only
sync_scope = "ASSESSMENT"  # Assessment data only
```

## 🔍 Checking Sync Status

### Recent Sync Results
```sql
SELECT TOP 100 
    AcademyCode,
    EndPoint,
    Result,
    RecordCount,
    LoggedAt
FROM sec.SyncResults
ORDER BY LoggedAt DESC;
```

### Failed Syncs
```sql
SELECT * 
FROM sec.SyncResults
WHERE Result = 0
AND LoggedAt >= date_sub(current_timestamp(), INTERVAL 7 DAYS)
ORDER BY LoggedAt DESC;
```

## 📊 Data Validation

### Student Counts by Academy
```sql
SELECT 
    Academy,
    DataSet,
    COUNT(*) as StudentCount
FROM base_students
GROUP BY Academy, DataSet
ORDER BY Academy;
```

### Latest Data Timestamp
```sql
SELECT 
    Academy,
    MAX(IngestedAt) as LastIngested,
    MAX(TransformedAt) as LastTransformed
FROM base_students
GROUP BY Academy;
```

## 🔧 Common Tasks

### Add New Academy
1. Store API key in Key Vault:
   ```bash
   az keyvault secret set \
     --vault-name "your-keyvault" \
     --name "g4s-api-key-XYZ" \
     --value "api-key-here"
   ```
2. Add to `sec.AcademySecurity`:
   ```sql
   INSERT INTO sec.AcademySecurity (...) VALUES (...);
   ```

### Disable Academy Temporarily
```sql
UPDATE sec.AcademySecurity
SET Active = 0
WHERE AcademyCode = 'ABC';
```

### Re-sync Single Academy
1. Disable all other academies temporarily
2. Run orchestration notebook
3. Re-enable academies

## 🛠️ Troubleshooting

### Error: Key Vault Access Denied
✅ Check workspace managed identity has "Get" permission on Key Vault
✅ Verify Key Vault URL format: `https://vaultname.vault.azure.net/`
✅ Test access: `notebookutils.credentials.getSecret('https://vaultname.vault.azure.net/', 'secret-name')`

### Error: Table Not Found
✅ Verify lakehouse attached to notebook
✅ Run raw ingestion before transformation

### Error: API Rate Limit
✅ Check G4S API status
✅ Add delays between academy processing
✅ Contact G4S support

### Slow Performance
✅ Optimize tables: `OPTIMIZE table_name ZORDER BY (Academy, DataSet)`
✅ Vacuum old files: `VACUUM table_name RETAIN 168 HOURS`
✅ Check Spark cluster size

Note: OPTIMIZE and VACUUM are Delta Lake commands, not standard SQL

## 📁 Key Tables

### Metadata
- `sec.AcademySecurity` - Academy configurations
- `sec.SyncResults` - Sync execution history

### Raw Layer (Bronze)
- `raw_g4s_student_details`
- `raw_g4s_departments`
- `raw_g4s_groups`
- etc.

### Base Layer (Silver)
- `base_students`
- `base_departments`
- `base_groups`
- etc.

## 🔐 Security

### Key Vault Secret Naming
Format: `g4s-api-key-{AcademyCode}`
Example: `g4s-api-key-ABC`

### Permissions Required
- Fabric workspace: Contributor or Admin
- Key Vault: Get Secret permission
- SQL endpoint: Read/Write on sec schema

## 🕐 Scheduled Sync

**Pipeline**: G4S Daily Sync
**Schedule**: Daily at 2:00 AM
**Duration**: ~30-60 minutes
**Notifications**: [Configure as needed]

## 📈 Monitoring Checklist

Daily:
- [ ] Check latest sync completed successfully
- [ ] Review error count in `sec.SyncResults`

Weekly:
- [ ] Review failed syncs and resolve
- [ ] Check data freshness by academy
- [ ] Verify record counts are reasonable

Monthly:
- [ ] Optimize Delta tables
- [ ] Vacuum old files
- [ ] Review performance metrics

## 🆘 Escalation Path

1. **Check Sync Results**: Review `sec.SyncResults` for error details
2. **Check Notebook Output**: Review cell outputs in Fabric
3. **Check Key Vault**: Verify secrets are accessible
4. **Check G4S API**: Verify API is responding
5. **Contact Technical Lead**: If issue persists
6. **Microsoft Support**: For Fabric/Azure issues
7. **G4S Support**: For API issues

## 📱 Quick Links

- Fabric Workspace: [URL]
- Key Vault: [URL]
- Documentation: See `fabric_notebooks/README.md`
- Migration Guide: See `fabric_notebooks/MIGRATION_GUIDE.md`

---

**Last Updated**: _______________
**Version**: 2.0 (Fabric/PySpark)
