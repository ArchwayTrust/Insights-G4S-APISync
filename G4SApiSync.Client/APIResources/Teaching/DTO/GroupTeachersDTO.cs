using Newtonsoft.Json;
using System.Collections.Generic;

namespace G4SApiSync.Client.DTOs
{
    public class GroupTeachersDTO
    {
        [JsonProperty("group_id")]
        public int G4SGroupId { get; set; }

        [JsonProperty("teacher_ids")]
        public IEnumerable<int> TeacherIDs { get; set; }


    }
}
