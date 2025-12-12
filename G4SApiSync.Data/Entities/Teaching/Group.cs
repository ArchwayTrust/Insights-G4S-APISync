using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;

namespace G4SApiSync.Data.Entities
{
    public class Group
    {
        [MaxLength(100)]
        [Key]
        public string GroupId { get; set; } //AcademyCode + DataSet + "-" + G4SGroupId

        [MaxLength(4)]
        public string DataSet { get; set; }

        [MaxLength(10)]
        public string Academy { get; set; }

        [MaxLength(1000)]
        public string Name { get; set; }

        [MaxLength(1000)]
        public string Code { get; set; }

        [MaxLength(100)]
        public string SubjectId { get; set; }

        public virtual Subject Subject { get; set; }

        public virtual ICollection<GroupStudent> GroupStudents { get; set; }

        public virtual ICollection<GroupTeacher> GroupTeachers { get; set; }

    }
}
