using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;

namespace G4SApiSync.Data.Entities
{
    public class GroupTeacher
    {
        [MaxLength(100)]
        public string GroupId { get; set; } //AcademyCode + DataSet + "-" + G4SGroupId

        [MaxLength(100)]
        public string TeacherId { get; set; } //AcademyCode + DataSet + "-" + G4STeacherId

        public virtual Teacher Teacher { get; set; }

        public virtual Group Group { get; set; }
    }
}
