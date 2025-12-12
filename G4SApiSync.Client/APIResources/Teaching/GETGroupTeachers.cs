using Newtonsoft.Json;
using System.Collections.Generic;
using System.ComponentModel.DataAnnotations.Schema;
using G4SApiSync.Client.DTOs;
using G4SApiSync.Data.Entities;
using G4SApiSync.Data;
using System.Threading.Tasks;
using System.Linq;
using System;
using System.Globalization;
using System.Data;
using Microsoft.Data.SqlClient;
using RestSharp;


namespace G4SApiSync.Client.EndPoints
{
    [JsonObject]
    public class GETGroupTeachers : IEndPoint<GroupTeachersDTO>, IDisposable
    {
        const string _endPoint = "/customer/v1/academic-years/{academicYear}/teaching/groups/teachers";
        private readonly string _connectionString;
        private readonly G4SContext _context;
        private readonly RestClient _client;

        public GETGroupTeachers(RestClient client, G4SContext context, string connectionString)
        {
            _context = context;
            _connectionString = connectionString;
            _client = client;
        }
        public string EndPoint
        {
            get { return _endPoint; }
        }

        // Replace the DTOs property with the correct type to match the interface
        [JsonProperty("group_teachers")]
        public IEnumerable<GroupTeachersDTO> DTOs { get; set; }

        [JsonProperty("has_more")]
        public bool HasMore { get; set; }

        [JsonProperty("cursor")]
        public int? Cursor { get; set; }

        public async Task<bool> UpdateDatabase(string APIKey, string AcYear, string AcademyCode, int? LowestYear = null, int? HighestYear = null, int? ReportId = null, DateTime? Date = null)
        {
            try
            {
                //Get data from G4S API
                APIRequest<GETGroupTeachers, GroupTeachersDTO> getGroupTeachers = new(_client, _endPoint, APIKey, AcYear);
                var groupTeachersDTO = getGroupTeachers.ToList();

                //Create datatable for group teachers.
                var dtGroupTeachers = new DataTable();
                dtGroupTeachers.Columns.Add("GroupId", typeof(String));
                dtGroupTeachers.Columns.Add("TeacherId", typeof(String));


                //Write the DTOs into the datatable.
                foreach (var groupTeacherDTO in groupTeachersDTO)
                {
                    foreach(var teacherId in groupTeacherDTO.TeacherIDs)
                    {
                        var row = dtGroupTeachers.NewRow();
                        row["GroupId"] = AcademyCode + AcYear + "-" + groupTeacherDTO.G4SGroupId.ToString();
                        row["TeacherId"] = AcademyCode + AcYear + "-" + teacherId.ToString();

                        dtGroupTeachers.Rows.Add(row);
                    }
                }

                //Removal dealt with in Groups end point.
                //Remove exisitng groups from SQL database
                //var currentGroups = _context.Groups.Where(i => i.DataSet == AcYear && i.Academy == AcademyCode);
                //_context.Groups.RemoveRange(currentGroups);
                //await _context.SaveChangesAsync();

                //Write datatable to sql
                using (var sqlBulk = new SqlBulkCopy(_connectionString))
                {
                    sqlBulk.ColumnMappings.Add("GroupId", "GroupId");
                    sqlBulk.ColumnMappings.Add("TeacherId", "TeacherId");

                    sqlBulk.DestinationTableName = "g4s.GroupTeachers";
                    sqlBulk.BulkCopyTimeout = 300;
                    sqlBulk.WriteToServer(dtGroupTeachers);
                }

                _context.SyncResults.Add(new SyncResult { AcademyCode = AcademyCode, EndPoint = _endPoint, LoggedAt = DateTime.Now, Result = true, DataSet = AcYear });
                await _context.SaveChangesAsync();
                return true;
            }
            catch (Exception e)
            {
                if (e.InnerException != null)
                {
                    _context.SyncResults.Add(new SyncResult { AcademyCode = AcademyCode, DataSet = AcYear, EndPoint = _endPoint, Exception = e.Message, InnerException = e.InnerException.Message, LoggedAt = DateTime.Now, Result = false });
                }
                else
                {
                    _context.SyncResults.Add(new SyncResult { AcademyCode = AcademyCode, DataSet = AcYear, EndPoint = _endPoint, Exception = e.Message, LoggedAt = DateTime.Now, Result = false });
                }

                await _context.SaveChangesAsync();
                return false;
            }
        }

        //Implements IDisposable
        public void Dispose() { Dispose(true); GC.SuppressFinalize(this); }
        protected virtual void Dispose(bool disposing)
        {
        }
    }

}
