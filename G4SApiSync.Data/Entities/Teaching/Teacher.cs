using System.Collections.Generic;
using System.ComponentModel.DataAnnotations;

namespace G4SApiSync.Data.Entities
{
    public class Teacher
    {
        [MaxLength(100)]
        [Key]
        public string TeacherId { get; set; } //AcademyCode + DataSet + "-" + G4STeacherId

        public int G4STeacherId { get; set; }

        [MaxLength(4)]
        public string DataSet { get; set; }

        [MaxLength(10)]
        public string Academy { get; set; }

        [MaxLength(10)]
        public string Title { get; set; }

        [MaxLength(100)]
        public string FirstName { get; set; }

        [MaxLength(100)]
        public string LastName { get; set; }

        [MaxLength(100)]
        public string PreferredFirstName { get; set; }

        [MaxLength(100)]
        public string PreferredLastName { get; set; }

        [MaxLength(100)]
        public string Initials { get; set; }

        [MaxLength(100)]
        public string Code { get; set; }

        public virtual ICollection<GroupTeacher> TeacherGroups { get; set; }

    }
}
