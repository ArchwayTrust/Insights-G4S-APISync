-- =============================================
-- Create SyncResults Tracking Table for Fabric
-- Tracks the execution history and results of API syncs
-- =============================================

IF OBJECT_ID('sec.SyncResults', 'U') IS NOT NULL
    DROP TABLE sec.SyncResults;
GO

CREATE TABLE sec.SyncResults (
    SyncResultId INT IDENTITY(1,1) PRIMARY KEY,
    AcademyCode NVARCHAR(10) NOT NULL,
    DataSet NVARCHAR(4) NULL,
    EndPoint NVARCHAR(500) NOT NULL,
    LoggedAt DATETIME2 NOT NULL DEFAULT GETUTCDATE(),
    Result BIT NOT NULL,
    RecordCount INT NULL,
    Exception NVARCHAR(MAX) NULL,
    InnerException NVARCHAR(MAX) NULL,
    
    -- Foreign key to AcademySecurity
    CONSTRAINT FK_SyncResults_AcademySecurity 
        FOREIGN KEY (AcademyCode) 
        REFERENCES sec.AcademySecurity(AcademyCode)
);
GO

-- Create indexes for common queries
CREATE INDEX IX_SyncResults_AcademyCode_LoggedAt 
ON sec.SyncResults(AcademyCode, LoggedAt DESC);

CREATE INDEX IX_SyncResults_EndPoint_LoggedAt 
ON sec.SyncResults(EndPoint, LoggedAt DESC);

CREATE INDEX IX_SyncResults_Result_LoggedAt 
ON sec.SyncResults(Result, LoggedAt DESC)
WHERE Result = 0;  -- Focus on failures
GO

PRINT 'SyncResults tracking table created successfully';
GO
