-- =============================================
-- Create AcademySecurity Metadata Table for Fabric
-- Modified to use Key Vault secret names instead of API keys
-- =============================================

-- Create schema if it doesn't exist
IF NOT EXISTS (SELECT * FROM sys.schemas WHERE name = 'sec')
BEGIN
    EXEC('CREATE SCHEMA sec');
END
GO

-- Drop table if exists (for clean deployment)
IF OBJECT_ID('sec.AcademySecurity', 'U') IS NOT NULL
    DROP TABLE sec.AcademySecurity;
GO

-- Create AcademySecurity table
CREATE TABLE sec.AcademySecurity (
    AcademyCode NVARCHAR(10) NOT NULL PRIMARY KEY,
    Name NVARCHAR(100) NULL,
    CurrentAcademicYear NVARCHAR(4) NULL,
    
    -- Key Vault secret name instead of API key
    KeyVaultSecretName NVARCHAR(100) NOT NULL,
    
    Active BIT NOT NULL DEFAULT 1,
    LowestYear INT NOT NULL DEFAULT 7,
    HighestYear INT NOT NULL DEFAULT 13,
    
    -- Attendance settings
    GetLessonAttendance BIT NOT NULL DEFAULT 0,
    GetSessionAttendance BIT NOT NULL DEFAULT 0,
    AttendanceFrom DATE NULL,
    AttendanceTo DATE NULL,
    
    -- Behaviour settings
    GetBehaviour BIT NOT NULL DEFAULT 0,
    BehaviourFrom DATE NULL,
    BehaviourTo DATE NULL,
    
    -- Audit columns
    CreatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    UpdatedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE()
);
GO

-- Create index on Active flag for faster queries
CREATE INDEX IX_AcademySecurity_Active 
ON sec.AcademySecurity(Active) 
WHERE Active = 1;
GO

-- Create trigger to update UpdatedAt timestamp
CREATE TRIGGER sec.TR_AcademySecurity_UpdatedAt
ON sec.AcademySecurity
AFTER UPDATE
AS
BEGIN
    SET NOCOUNT ON;
    
    UPDATE sec.AcademySecurity
    SET UpdatedAt = GETUTCDATE()
    FROM sec.AcademySecurity AS t
    INNER JOIN inserted AS i ON t.AcademyCode = i.AcademyCode;
END;
GO

-- =============================================
-- Sample data insert (UPDATE WITH YOUR VALUES)
-- =============================================

-- Example: Insert academy configuration
-- The KeyVaultSecretName should match the secret name in your Azure Key Vault
/*
INSERT INTO sec.AcademySecurity 
    (AcademyCode, Name, CurrentAcademicYear, KeyVaultSecretName, Active, 
     LowestYear, HighestYear, GetLessonAttendance, GetSessionAttendance, 
     AttendanceFrom, AttendanceTo, GetBehaviour, BehaviourFrom, BehaviourTo)
VALUES 
    ('ABC', 'Academy Name', '2324', 'g4s-api-key-abc', 1, 
     7, 13, 1, 1, 
     '2023-09-01', '2024-07-31', 1, '2023-09-01', '2024-07-31');
*/

-- =============================================
-- Grant permissions (adjust as needed for your environment)
-- =============================================

-- Grant read access to data analysts/engineers
-- GRANT SELECT ON sec.AcademySecurity TO [FabricDataEngineers];

-- Grant write access to ETL service accounts
-- GRANT SELECT, INSERT, UPDATE, DELETE ON sec.AcademySecurity TO [FabricETLService];

PRINT 'AcademySecurity table created successfully';
PRINT 'Remember to:';
PRINT '1. Insert your academy configurations';
PRINT '2. Store API keys in Azure Key Vault with names matching KeyVaultSecretName column';
PRINT '3. Grant appropriate permissions to Fabric service principals';
GO
