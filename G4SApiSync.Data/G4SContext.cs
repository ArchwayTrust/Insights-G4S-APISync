using G4SApiSync.Data.Entities;
using Microsoft.EntityFrameworkCore;
using System;


namespace G4SApiSync.Data
{
    public class G4SContext : DbContext
    {
        public G4SContext(DbContextOptions<G4SContext> options) : base(options)
        {
        }

        protected override void OnConfiguring(DbContextOptionsBuilder optionsBuilder)
        {
        }

        //Academy List
        public virtual DbSet<AcademySecurity> AcademySecurity { get; set; }
        public virtual DbSet<SyncResult> SyncResults { get; set; }

        //Students
        public virtual DbSet<Student> Students { get; set; }
        public virtual DbSet<EducationDetail> EducationDetails { get; set; }
        public virtual DbSet<StudentAttribute> StudentAttributes { get; set; }
        public virtual DbSet<StudentAttributeValue> StudentAttributeValues { get; set; }
        public virtual DbSet<AttributeType> AttributeTypes { get; set; }
        public virtual DbSet<AttributeValue> AttributeValues { get; set; }

        //Assessment
        public virtual DbSet<Marksheet> Marksheets { get; set; }
        public virtual DbSet<MarksheetGrade> MarksheetGrades { get; set; }
        public virtual DbSet<Markslot> Markslots { get; set; }
        public virtual DbSet<MarkslotMark> MarkslotMarks { get; set; }

        //Teaching
        public virtual DbSet<Department> Departments { get; set; }
        public virtual DbSet<Subject> Subjects { get; set; }
        public virtual DbSet<Group> Groups { get; set; }
        public virtual DbSet<GroupStudent> GroupStudents { get; set; }
        public virtual DbSet<GroupTeacher> GroupTeachers { get; set; }
        public virtual DbSet<Teacher> Teachers { get; set; }


        //Attainment
        public virtual DbSet<PriorAttainment> PriorAttainment { get; set; }

        public virtual DbSet<GradeName> GradeNames { get; set; }

        public virtual DbSet<GradeType> GradeTypes { get; set; }

        public virtual DbSet<Grade> Grades { get; set; }

        public virtual DbSet<ExamResult> ExamResults { get; set; }

        //Attendance
        public virtual DbSet<StudentSessionSummary> StudentSessionSummaries { get; set; }
        public virtual DbSet<AttendanceCode> AttendanceCodes { get; set; }
        public virtual DbSet<AttendanceAliasCode> AttendanceAliasCodes { get; set; }
        public virtual DbSet<StudentLessonMark> StudentLessonMarks { get; set; }
        public virtual DbSet<StudentSessionMark> StudentSessionMarks { get; set; }

        //Timetables
        public virtual DbSet<Period> Periods { get; set; }
        public virtual DbSet<TTClass> TTClasses { get; set; }
        public virtual DbSet<Calendar> Calendar { get; set; }

        //Behaviour
        public virtual DbSet<BehClassification> BehClassifications { get; set; }
        public virtual DbSet<BehEventType> BehEventTypes { get; set; }
        public virtual DbSet<BehEvent> BehEvents { get; set; }
        public virtual DbSet<BehEventStudent> BehEventStudents { get; set; }

        //Users
        public virtual DbSet<Staff> Staff { get; set; }

        //Fluent API Configuration
        protected override void OnModelCreating(ModelBuilder modelBuilder)
        {
            if (modelBuilder == null)
            {
                throw new ArgumentNullException(nameof(modelBuilder));
            }

            modelBuilder.HasDefaultSchema("g4s");

            //Students

            modelBuilder.Entity<EducationDetail>()
                .HasOne(b => b.Student)
                .WithOne(c => c.EducationDetail)
                .HasForeignKey<EducationDetail>(s => s.StudentId);

            modelBuilder.Entity<StudentAttribute>()
                .HasOne<EducationDetail>(b => b.EducationDetail)
                .WithMany(c => c.StudentAttributes)
                .HasForeignKey(s => s.StudentId)
                .OnDelete(DeleteBehavior.Cascade);


            modelBuilder.Entity<StudentAttributeValue>()
                .HasOne<StudentAttribute>(b => b.StudentAttribute)
                .WithMany(c => c.StudentAttributeValues)
                .HasForeignKey(s => s.StudentAttributeId)
                .OnDelete(DeleteBehavior.Cascade);

            //modelBuilder.Entity<AttributeValue>()
            //    .HasKey(pc => new { pc.StudentId, pc.AttributeTypeId });

            modelBuilder.Entity<AttributeValue>()
                .HasOne<AttributeType>(b => b.AttributeType)
                .WithMany(c => c.AttributeValues)
                .HasForeignKey(s => s.AttributeTypeId)
                .OnDelete(DeleteBehavior.Cascade);

            modelBuilder.Entity<AttributeValue>()
                .HasOne<Student>(b => b.Student)
                .WithMany(c => c.AttributeValues)
                .HasForeignKey(s => s.StudentId)
                .OnDelete(DeleteBehavior.Cascade);

            //Teaching
            modelBuilder.Entity<GroupStudent>()
                .HasKey(pc => new { pc.StudentId, pc.GroupId });

            modelBuilder.Entity<GroupTeacher>()
                .HasKey(pc => new { pc.TeacherId, pc.GroupId });

            modelBuilder.Entity<Subject>()
                .HasOne<Department>(b => b.Department)
                .WithMany(c => c.Subjects)
                .HasForeignKey(s => s.DepartmentId)
                .OnDelete(DeleteBehavior.Cascade);

            modelBuilder.Entity<Group>()
                .HasOne<Subject>(b => b.Subject)
                .WithMany(c => c.Groups)
                .HasForeignKey(s => s.SubjectId)
                .OnDelete(DeleteBehavior.Cascade);

            modelBuilder.Entity<GroupStudent>()
                .HasOne<Group>(b => b.Group)
                .WithMany(c => c.GroupStudents)
                .HasForeignKey(s => s.GroupId)
                .OnDelete(DeleteBehavior.Cascade);

            modelBuilder.Entity<GroupStudent>()
                .HasOne<Student>(b => b.Student)
                .WithMany(c => c.StudentGroups)
                .HasForeignKey(s => s.StudentId)
                .OnDelete(DeleteBehavior.Cascade);

            modelBuilder.Entity<GroupTeacher>()
                .HasOne<Group>(b => b.Group)
                .WithMany(c => c.GroupTeachers)
                .HasForeignKey(s => s.GroupId)
                .OnDelete(DeleteBehavior.Cascade);

            modelBuilder.Entity<GroupTeacher>()
                .HasOne<Teacher>(b => b.Teacher)
                .WithMany(c => c.TeacherGroups)
                .HasForeignKey(s => s.TeacherId)
                .OnDelete(DeleteBehavior.Cascade);

            //Assessment
            modelBuilder.Entity<MarksheetGrade>()
                .HasKey(pc => new { pc.StudentId, pc.MarksheetId });

            modelBuilder.Entity<MarkslotMark>()
                .HasKey(pc => new { pc.StudentId, pc.MarkslotId });

            modelBuilder.Entity<Marksheet>()
                .HasOne<Subject>(b => b.Subject)
                .WithMany(c => c.Marksheets)
                .HasForeignKey(s => s.SubjectId)
                .OnDelete(DeleteBehavior.Cascade);

            modelBuilder.Entity<Markslot>()
                .HasOne<Marksheet>(b => b.Marksheet)
                .WithMany(c => c.Markslots)
                .HasForeignKey(s => s.MarksheetId)
                .OnDelete(DeleteBehavior.Cascade);

            modelBuilder.Entity<MarksheetGrade>()
                .HasOne<Marksheet>(b => b.Marksheet)
                .WithMany(c => c.MarksheetGrades)
                .HasForeignKey(s => s.MarksheetId)
                .OnDelete(DeleteBehavior.Cascade);

            modelBuilder.Entity<MarksheetGrade>()
                .HasOne<Student>(b => b.Student)
                .WithMany(c => c.MarksheetGrades)
                .HasForeignKey(s => s.StudentId)
                .OnDelete(DeleteBehavior.Cascade);

            modelBuilder.Entity<MarkslotMark>()
                .HasOne<Student>(b => b.Student)
                .WithMany(c => c.MarkslotMarks)
                .HasForeignKey(s => s.StudentId)
                .OnDelete(DeleteBehavior.Cascade);

            modelBuilder.Entity<MarkslotMark>()
                .HasOne<Markslot>(b => b.Markslot)
                .WithMany(c => c.MarkslotMarks)
                .HasForeignKey(s => s.MarkslotId)
                .OnDelete(DeleteBehavior.Cascade);

            //Attainment
            modelBuilder.Entity<PriorAttainment>()
                .HasKey(pc => new { pc.StudentId, pc.Code });

            modelBuilder.Entity<Grade>()
                .HasKey(pc => new { pc.StudentId, pc.GradeTypeId, pc.SubjectId });

            modelBuilder.Entity<PriorAttainment>()
                .HasOne<Student>(b => b.Student)
                .WithMany(c => c.PriorAttainment)
                .HasForeignKey(s => s.StudentId)
                .OnDelete(DeleteBehavior.Cascade);

            modelBuilder.Entity<Grade>()
                .HasOne<Student>(b => b.Student)
                .WithMany(c => c.Grades)
                .HasForeignKey(s => s.StudentId)
                .OnDelete(DeleteBehavior.Cascade);

            modelBuilder.Entity<Grade>()
                .HasOne<GradeType>(b => b.GradeType)
                .WithMany(c => c.Grades)
                .HasForeignKey(s => s.GradeTypeId)
                .OnDelete(DeleteBehavior.Cascade);

            modelBuilder.Entity<Grade>()
                .HasOne<Subject>(b => b.Subject)
                .WithMany(c => c.Grades)
                .HasForeignKey(s => s.SubjectId)
                .OnDelete(DeleteBehavior.Cascade);

            modelBuilder.Entity<ExamResult>()
                .HasOne<Student>(b => b.Student)
                .WithMany(c => c.ExamResults)
                .HasForeignKey(s => s.StudentId)
                .OnDelete(DeleteBehavior.Cascade);

            modelBuilder.Entity<ExamResult>()
                .HasOne<Subject>(b => b.Subject)
                .WithMany(c => c.ExamResults)
                .HasForeignKey(s => s.SubjectId)
                .OnDelete(DeleteBehavior.Cascade);

            modelBuilder.Entity<GradeType>()
                .HasData(
                    new { GradeTypeId = 1, Name = "External target" },
                    new { GradeTypeId = 2, Name = "Teacher target" },
                    new { GradeTypeId = 3, Name = "Combined target" },
                    new { GradeTypeId = 4, Name = "Current" },
                    new { GradeTypeId = 5, Name = "Project" },
                    new { GradeTypeId = 6, Name = "Actual" },
                    new { GradeTypeId = 7, Name = "Honest" },
                    new { GradeTypeId = 8, Name = "Aspirational" },
                    new { GradeTypeId = 9, Name = "Additional target" },
                    new { GradeTypeId = 10, Name = "Baseline grade" });

            //Attendance
            modelBuilder.Entity<StudentSessionSummary>()
                .HasOne(b => b.Student)
                .WithOne(c => c.StudentSessionSummary)
                .HasForeignKey<StudentSessionSummary>(s => s.StudentId);

            modelBuilder.Entity<AttendanceAliasCode>()
                .HasOne(b => b.AttendanceCode)
                .WithMany(c => c.AttendanceAliasCodes)
                .HasForeignKey(s => s.AttendanceCodeId)
                .OnDelete(DeleteBehavior.Cascade);

            modelBuilder.Entity<StudentLessonMark>()
                .HasKey(pc => new { pc.StudentId, pc.Date, pc.ClassId });

            modelBuilder.Entity<StudentSessionMark>()
                .HasKey(pc => new { pc.StudentId, pc.Date, pc.Session });


            //Behaviour

            //modelBuilder.Entity<BehEvent>()
            //     .HasOne<BehEventType>(b => b.BehEventType)
            //     .WithMany(c => c.BehEvents)
            //     .HasForeignKey(s => s.BehEventTypeId)
            //     .OnDelete(DeleteBehavior.);

            //modelBuilder.Entity<BehEventType>()
            //     .HasOne<BehClassification>(b => b.BehClassification)
            //     .WithMany(c => c.BehEventTypes)
            //     .HasForeignKey(s => s.BehClassificationId)
            //     .OnDelete(DeleteBehavior.ClientNoAction);

            modelBuilder.Entity<BehEventStudent>()
                 .HasOne<BehEvent>(b => b.BehEvent)
                 .WithMany(c => c.EventStudents)
                 .HasForeignKey(s => s.BehEventId)
                 .OnDelete(DeleteBehavior.Cascade);

            modelBuilder.Entity<BehEventStudent>()
                   .HasKey(pc => new { pc.BehEventId, pc.StudentId });

            //Timetables
            modelBuilder.Entity<Calendar>()
                .HasKey(pc => new { pc.Academy, pc.DataSet, pc.Date });

            //API Keys
            modelBuilder.Entity<AcademySecurity>()
                .ToTable("AcademySecurity", "sec");
        }
    }
}