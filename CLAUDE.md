# CLAUDE.md

Guidance for working in this repository. This is an architecture/orientation guide for making
changes — for end-user setup and operation, see [README.md](README.md).

## Overview

**G4S API Sync** is a .NET 9 console application that pulls educational data from the
[Go4Schools](https://www.go4schools.com/) ("G4S") REST API and bulk-loads it into a local Microsoft
SQL Server database. It is an ETL job for a multi-academy trust: it loops over every active academy,
calls each G4S endpoint, and writes the results into the `g4s` schema. It runs as a scheduled console
`.exe` (Windows Task Scheduler) on the database server — there is no UI and no long-running service.

Stack: **.NET 9**, **Entity Framework Core 9** (SQL Server), **RestSharp** (HTTP), **Newtonsoft.Json**
(deserialization). Solution file: `G4SApiSync.sln`.

## Solution layout

Three projects:

| Project | Responsibility |
|---|---|
| [G4SApiSync/](G4SApiSync/) | Console host & entry point. [Program.cs](G4SApiSync/Program.cs) builds config + DI, applies EF migrations, and routes the run by CLI argument. Holds [appsettings.json](G4SApiSync/appsettings.json), `SQL Scripts/`, and `SQL Examples Queries/`. |
| [G4SApiSync.Client/](G4SApiSync.Client/) | API integration, transformation, and DB writes. The orchestrator [GetAndStoreAllData.cs](G4SApiSync.Client/GetAndStoreAllData.cs), the generic paginated HTTP caller [APIRequest.cs](G4SApiSync.Client/APIRequest.cs), and one `GETxxx.cs` class per endpoint under `APIResources/<Domain>/`. |
| [G4SApiSync.Data/](G4SApiSync.Data/) | EF Core data layer. [G4SContext.cs](G4SApiSync.Data/G4SContext.cs) (DbContext), entities under `Entities/<Domain>/`, and `Migrations/`. |

Both the client and the data layer are organised by the same **domain folders**: `Students`,
`Teaching`, `Assessment`, `Attainment`, `Attendance`, `Timetables`, `Behaviour`, `Users` (the client
also has a `Schools` folder, which has no matching entity). When adding work, keep the new files in the
matching domain folder on both sides.

## How a sync runs (data flow)

```
Program.Main(args)
  └─ ConfigureServices: load appsettings.json → DbContext → Database.Migrate()
  └─ RunApiSync / RunApiAttendanceSync / RunApiBehaviourSync   (chosen by CLI arg)
       └─ GetAndStoreAllData.SyncXxx()                          (one method per domain)
            └─ foreach active academy:
                 └─ GETxxx.UpdateDatabase(apiKey, acYear, academyCode, ...)
                      └─ APIRequest<EndPoint, DTO>.ToList()      (Bearer GET, cursor pagination)
                      └─ map DTO → DataTable
                      └─ delete existing rows for this academy + academic year
                      └─ SqlBulkCopy → g4s.<Table>
                      └─ write a SyncResult row (success/failure + exception)
```

Each `SyncResult` is also printed to the console as the run progresses, so the scheduled task's output
is the run log.

**Three run modes** (see [Program.cs](G4SApiSync/Program.cs)):

- no argument → **full sync** (Students → Teaching → Assessment → Attainment → Attendance → Timetable → Behaviour → Users)
- `ATT` → **attendance only**
- `BEH` → **attendance + behaviour**

The active-academy list, API keys, academic year, and the behaviour/attendance feature flags all come
from the `sec.AcademySecurity` table, loaded once in the `GetAndStoreAllData` constructor (`Active == true`).

## The endpoint pattern — adding or changing a synced endpoint

This is the codebase's core repeating pattern; almost every change is a variation of it. A good
reference pair is [GETStudentDetails.cs](G4SApiSync.Client/APIResources/Students/GETStudentDetails.cs)
and [StudentDTO.cs](G4SApiSync.Client/APIResources/Students/DTO/StudentDTO.cs). To add a new endpoint
you touch **four places**:

1. **DTO** — add a class in `APIResources/<Domain>/DTO/` with Newtonsoft `[JsonProperty("...")]`
   attributes matching the API's JSON field names (the API uses `snake_case`).

2. **Endpoint class** — add `GETxxx.cs` in `APIResources/<Domain>/` implementing
   [IEndPoint&lt;DTO&gt;](G4SApiSync.Client/Interfaces/IEndPoint.cs). It declares:
   - `const string _endPoint` — the URL template, e.g. `"/customer/v1/academic-years/{academicYear}/students"`.
   - the pagination/deserialization properties `DTOs` (`[JsonProperty]` named after the JSON array),
     `HasMore`, `Cursor`.
   - `UpdateDatabase(...)`, which: calls `new APIRequest<GETxxx, XxxDTO>(...).ToList()`, builds a
     `DataTable`, **deletes existing rows for this academy + academic year**, runs `SqlBulkCopy` into
     the target `g4s.<Table>`, and records a `SyncResult`. Wrap the body in try/catch — on failure it
     logs a failed `SyncResult` and returns `false` rather than throwing.

3. **Entity + schema** — add an EF entity in `G4SApiSync.Data/Entities/<Domain>/`, expose it as a
   `DbSet` in [G4SContext.cs](G4SApiSync.Data/G4SContext.cs), configure keys/relationships in
   `OnModelCreating`, then add a migration via the Visual Studio Package Manager Console
   (`Add-Migration <Name>`, with the Default Project set to `G4SApiSync.Data` — see
   [AddMigrationReadme.md](G4SApiSync.Data/AddMigrationReadme.md)). Migrations auto-apply on the next
   run via `Database.Migrate()`, so there's no separate `Update-Database`/deploy step against production.

4. **Wire it in** — call the new `GETxxx` from the matching `SyncXxx()` method in
   [GetAndStoreAllData.cs](G4SApiSync.Client/GetAndStoreAllData.cs), following the existing
   `foreach (var academy in _academyList)` blocks.

`APIRequest.ToList()` handles cursor pagination transparently and applies a `Thread.Sleep(200)`
between calls to be gentle on the API.

## Configuration & secrets

- **[appsettings.json](G4SApiSync/appsettings.json)** contains *only* the SQL connection string and
  uses Windows/Trusted authentication — no credentials are stored. It is copied to the build output.
- **`sec.AcademySecurity` (SQL table)** holds everything per-academy: `APIKey`, `AcademyCode`,
  `CurrentAcademicYear`, `Active`, `LowestYear`/`HighestYear`, and the feature flags
  `GetBehaviour` / `GetSessionAttendance` / `GetLessonAttendance` with their optional
  `BehaviourFrom`/`BehaviourTo` and `AttendanceFrom`/`AttendanceTo` date ranges. Edit it via SSMS — the
  README documents the steps. **No API keys live in source control.**

## Database

- Default schema is `g4s`; configuration is `sec`.
- Schema is managed by **EF Core migrations** (`G4SApiSync.Data/Migrations/`) and applied
  automatically at startup via `_context.Database.Migrate()` — the first run creates or upgrades the DB.
- After first setup, run the scripts in `G4SApiSync/SQL Scripts/` to create helper views and set the
  database to simple recovery (keeps the log file from growing). `SQL Examples Queries/` has read
  examples.
- **`SyncResults`** is the run log: one row per endpoint per academy per run, recording success/failure
  and any exception.

## Build, release & deploy

- **CI build:** [.github/workflows/build-and-release.yml](.github/workflows/build-and-release.yml) runs
  on push to `main` — `dotnet publish` the console app, zip with a timestamped version, and create a
  GitHub Release with the zip.
- **Deploy:** [.github/workflows/deploy-onpremise.yml](.github/workflows/deploy-onpremise.yml) runs on
  release publish or manual `workflow_dispatch`, on a **self-hosted Windows runner**. It downloads the
  latest release, backs up the current deployment, and copies the new build to the network share
  `\\core-dw-files\Deployment\G4SAPISync`.
- **Scheduling:** Windows Task Scheduler on the DB server invokes `G4SApiSync.exe` (with `ATT` / `BEH`
  / no arg for the desired mode).
- There are **no automated tests** and **no infrastructure-as-code** in this repo.

## Conventions & gotchas

- **Composite keys:** row IDs are built like `AcademyCode + AcYear + "-" + id` (e.g. `StudentId`), so
  the same G4S id from different academies/years never collides.
- **`DataSet` + `Academy` tagging:** every table carries the academic year (`DataSet`) and `Academy`
  code, so multiple academies and multiple years coexist in one table. Changing `CurrentAcademicYear`
  in `sec.AcademySecurity` pulls a prior year without overwriting the current one.
- **Full rewrite, not upsert:** `UpdateDatabase` deletes all rows for the current academy + year and
  bulk-inserts fresh data each run. Date-ranged syncs (attendance/behaviour) delete and reload per day
  in the range.
- **Dates:** API timestamps are parsed with `DateTime.ParseExact(value, "yyyy-MM-ddTHH:mm:ssZ", CultureInfo.InvariantCulture)`.
- **Deserialization fallback:** `APIRequest.ToList()` tries the paginated envelope first, then a bare
  `List<DTO>`, then a single `DTO` — handy to know when an endpoint shape differs from the norm.
- **Errors are recorded, not thrown:** each endpoint's try/catch writes a failed `SyncResult` and
  returns `false`, so one bad endpoint/academy doesn't abort the whole sync. There is no retry — that's
  the scheduler's job.
- **British spelling** is used throughout (e.g. `Behaviour`); keep new names consistent.
