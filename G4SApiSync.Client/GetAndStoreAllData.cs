using G4SApiSync.Client.EndPoints;
using G4SApiSync.Data;
using G4SApiSync.Data.Entities;
using RestSharp;
using System;
using System.Collections.Generic;
using System.Linq;
using System.Text;
using System.Threading.Tasks;

namespace G4SApiSync.Client
{
    public class GetAndStoreAllData
    {
        private readonly List<AcademySecurity> _academyList;
        private readonly G4SContext _context;
        private readonly string _connectionString;
        private readonly RestClient _client;

        public GetAndStoreAllData(G4SContext context, string connectionString)
        {
            _context = context;
            _connectionString = connectionString;

            var restOptions = new RestClientOptions("https://api.go4schools.com")
            {
                ThrowOnAnyError = true
            };

            _client = new RestClient(restOptions);

            _academyList = _context.AcademySecurity.Where(i => i.Active == true).ToList();
        }

        //Sync Students
        public async Task<List<SyncResult>> SyncStudents()
        {
            List<SyncResult> syncResults = new();

            //GET Student Details
            foreach (var academy in _academyList)
            {
                using GETStudentDetails getStudentDetails = new(_client, _context, _connectionString);
                bool result = await getStudentDetails.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getStudentDetails.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });
            }

            //GET Education Details
            foreach (var academy in _academyList)
            {
                using GETEducationDetails getEducationDetails = new(_client, _context, _connectionString);
                bool result = await getEducationDetails.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getEducationDetails.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });

            }

            //GET General Attributes
            foreach (var academy in _academyList)
            {
                using GETGeneralAttributes getGeneralAttributes = new(_client, _context, _connectionString);
                bool result = await getGeneralAttributes.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getGeneralAttributes.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });

            }

            //GET Demographic Attributes
            foreach (var academy in _academyList)
            {
                using GETDemographicAttributes getDemographicAttributes = new(_client, _context, _connectionString);
                bool result = await getDemographicAttributes.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getDemographicAttributes.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });

            }

            //GET Send Attributes
            foreach (var academy in _academyList)
            {
                using GETSendAttributes getSendAttributes = new(_client, _context, _connectionString);
                bool result = await getSendAttributes.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getSendAttributes.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });
            }

            //GET Sensitive Attributes
            foreach (var academy in _academyList)
            {
                using GETSensitiveAttributes getSensitiveAttributes = new(_client, _context, _connectionString);
                bool result = await getSensitiveAttributes.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getSensitiveAttributes.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });

            }


            return syncResults;
        }

        //Sync Teaching
        public async Task<List<SyncResult>> SyncTeaching()
        {
            List<SyncResult> syncResults = new();

            //GET Departments
            foreach (var academy in _academyList)
            {
                using GETDepartments getDepartments = new(_client, _context, _connectionString);
                bool result = await getDepartments.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getDepartments.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });
            }

            //GET Subjects
            foreach (var academy in _academyList)
            {
                using GETSubjects getSubjects = new(_client, _context, _connectionString);
                bool result = await getSubjects.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getSubjects.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });
            }

            //GET Groups
            foreach (var academy in _academyList)
            {
                using GETGroups getGroups = new(_client, _context, _connectionString);
                bool result = await getGroups.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getGroups.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });

            }

            //GET Group Students
            foreach (var academy in _academyList)
            {
                using GETGroupStudents getGroupStudents = new(_client, _context, _connectionString);
                bool result = await getGroupStudents.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getGroupStudents.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });
            }

            //GET Teachers
            foreach (var academy in _academyList)
            {
                using GETTeachers getTeachers = new(_client, _context, _connectionString);
                bool result = await getTeachers.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getTeachers.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });
            }

            //GET Group Teachers
            foreach (var academy in _academyList)
            {
                using GETGroupTeachers getGroupTeachers = new(_client, _context, _connectionString);
                bool result = await getGroupTeachers.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getGroupTeachers.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });
            }

            return syncResults;
        }

        //Sync Assessments
        public async Task<List<SyncResult>> SyncAssessment()
        {
            List<SyncResult> syncResults = new();

            //GET Markbooks
            foreach (var academy in _academyList)
            {
                using GETMarkbooks getMarkbooks = new(_client, _context, _connectionString);
                bool result = await getMarkbooks.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getMarkbooks.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });

            }

            //GET Marksheet Grades
            foreach (var academy in _academyList)
            {
                using GETMarksheetGrades getMarksheetGrades = new(_client, _context, _connectionString);
                bool result = await getMarksheetGrades.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getMarksheetGrades.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });

            }

            //GET Markslot Marks
            foreach (var academy in _academyList)
            {
                using GETMarkslotMarks getMarkslotMarks = new(_client, _context, _connectionString);
                bool result = await getMarkslotMarks.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getMarkslotMarks.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });
            }

            return syncResults;
        }

        //Sync Attainment
        public async Task<List<SyncResult>> SyncAttainment()
        {
            List<SyncResult> syncResults = new();

            //GET Prior Attainment
            foreach (var academy in _academyList)
            {
                using GETPriorAttainment getPA = new(_client, _context, _connectionString);
                bool result = await getPA.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getPA.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });

            }

            //GET Grade Names
            foreach (var academy in _academyList)
            {
                using GETGradeNames getGradeName = new(_client, _context, _connectionString);
                bool result = await getGradeName.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode, academy.LowestYear, academy.HighestYear);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getGradeName.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });

            }

            //GET Grades
            foreach (var academy in _academyList)
            {
                using GETGrades getGrades = new(_client, _context, _connectionString);
                bool result = await getGrades.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode, academy.LowestYear, academy.HighestYear);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getGrades.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });
            }


            //GET Exam Results
            foreach (var academy in _academyList)
            {
                using GETExamResults getExamResults = new(_client, _context, _connectionString);
                bool result = await getExamResults.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode, academy.LowestYear, academy.HighestYear);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getExamResults.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });
            }

            return syncResults;
        }
        //Sync Attendance
        public async Task<List<SyncResult>> SyncAttendance()
        {
            List<SyncResult> syncResults = new();

            //GET Student Session Summary
            foreach (var academy in _academyList)
            {
                using GETStudentSessionSummaries getStudentSessionSummaries = new(_client, _context, _connectionString);
                bool result = await getStudentSessionSummaries.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getStudentSessionSummaries.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });
            }

            //GET Attendance Codes
            foreach (var academy in _academyList)
            {
                using GETAttendanceCodes getAttendanceCodes = new(_client, _context, _connectionString);
                bool result = await getAttendanceCodes.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getAttendanceCodes.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });
            }

            //GET Lesson Attendance
            foreach (var academy in _academyList)
            {
                bool getAttendance = academy.GetLessonAttendance;
                DateTime fromDate;
                DateTime toDate;

                if (academy.AttendanceFrom != null)
                {
                    fromDate = academy.AttendanceFrom.Value;
                }
                else
                {
                    fromDate = DateTime.Now.Date.AddDays(-1);
                }

                if (academy.AttendanceTo != null)
                {
                    toDate = academy.AttendanceTo.Value;
                }
                else
                {
                    toDate = DateTime.Now.Date.AddDays(-1);
                }


                if (getAttendance)
                {
                    var dates = Enumerable.Range(0, (toDate - fromDate).Days + 1)
                                    .Select(day => fromDate.AddDays(day));

                    foreach (var dt in dates)
                    {
                        using GETStudentLessonMarks getStudentLessonMarks = new(_client, _context, _connectionString);
                        bool result = await getStudentLessonMarks.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode, null, null, null, dt);
                        syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getStudentLessonMarks.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });
                    }
                }

            }

            //GET Session Attendance
            foreach (var academy in _academyList)
            {
                bool getAttendance = academy.GetSessionAttendance;
                DateTime fromDate;
                DateTime toDate;

                if (academy.AttendanceFrom != null)
                {
                    fromDate = academy.AttendanceFrom.Value;
                }
                else
                {
                    fromDate = DateTime.Now.Date.AddDays(-7);
                }

                if (academy.AttendanceTo != null)
                {
                    toDate = academy.AttendanceTo.Value;
                }
                else
                {
                    toDate = DateTime.Now;
                }


                if (getAttendance)
                {
                    var dates = Enumerable.Range(0, (toDate - fromDate).Days + 1)
                                    .Select(day => fromDate.AddDays(day));

                    foreach (var dt in dates)
                    {
                        using GETStudentSessionMarks getStudentSessionMarks = new(_client, _context, _connectionString);
                        bool result = await getStudentSessionMarks.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode, null, null, null, dt);
                        syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getStudentSessionMarks.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });
                    }
                }

            }

            return syncResults;
        }

        //Sync Timetable
        public async Task<List<SyncResult>> SyncTimetable()
        {
            List<SyncResult> syncResults = new();

            //GET Periods
            foreach (var academy in _academyList)
            {
                using GETPeriods getPeriods = new(_client, _context, _connectionString);
                bool result = await getPeriods.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getPeriods.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });

            }

            //GET TT Classes
            foreach (var academy in _academyList)
            {
                using GETTTClasses getTTClasses = new(_client, _context, _connectionString);
                bool result = await getTTClasses.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getTTClasses.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });

            }

            //GET Calendar
            foreach (var academy in _academyList)
            {
                using GETCalendar getCalendar = new(_client, _context, _connectionString);
                bool result = await getCalendar.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getCalendar.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });

            }

            return syncResults;
        }

        //Sync Behaviour
        public async Task<List<SyncResult>> SyncBehaviour()
        {
            List<SyncResult> syncResults = new();

            // GET Behaviour Classifications
            foreach (var academy in _academyList)
            {
                bool getBehaviour = academy.GetBehaviour;
                if (getBehaviour)
                {
                    using GETBehClassifications getBehClassifications = new(_client, _context, _connectionString);
                    bool result = await getBehClassifications.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                    syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getBehClassifications.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });
                }

            }

            // GET Behaviour Event Types
            foreach (var academy in _academyList)
            {
                bool getBehaviour = academy.GetBehaviour;
                if (getBehaviour)
                {
                    using GETBehEventTypes getBehEventTypes = new(_client, _context, _connectionString);
                    bool result = await getBehEventTypes.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                    syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getBehEventTypes.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });
                }

            }

            //GET Behaviour Events
            foreach (var academy in _academyList)
            {
                bool getBehaviour = academy.GetBehaviour;
                DateTime fromDate;
                DateTime toDate;

                if (academy.BehaviourFrom != null)
                {
                    fromDate = academy.BehaviourFrom.Value;
                }
                else
                {
                    fromDate = DateTime.Now.Date.AddDays(-14);
                }

                if (academy.BehaviourTo != null)
                {
                    toDate = academy.BehaviourTo.Value;
                }
                else
                {
                    toDate = DateTime.Now.Date;
                }


                if (getBehaviour)
                {
                    var dates = Enumerable.Range(0, (toDate - fromDate).Days + 1)
                                    .Select(day => fromDate.AddDays(day));

                    foreach (var dt in dates)
                    {
                        using GETBehEvents getBehEvents = new(_client, _context, _connectionString);
                        bool result = await getBehEvents.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode, null, null, null, dt);
                        syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getBehEvents.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = academy.CurrentAcademicYear });
                    }
                }

            }

            return syncResults;

        }


        //Sync Users
        public async Task<List<SyncResult>> SyncUsers()
        {
            List<SyncResult> syncResults = new();

            // GET Staff
            foreach (var academy in _academyList)
            {
                using GETStaff getStaff = new(_client, _context, _connectionString);
                bool result = await getStaff.UpdateDatabase(academy.APIKey, academy.CurrentAcademicYear, academy.AcademyCode);
                syncResults.Add(new SyncResult { AcademyCode = academy.AcademyCode, EndPoint = getStaff.EndPoint, Result = result, LoggedAt = DateTime.Now, DataSet = "N/A" });

            }
            return syncResults;
        }
    }
}
