from django.db import models


# ----------------------------
# CORE ACADEMIC STRUCTURE
# ----------------------------

class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)

    class Meta:
        indexes = [
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return self.name


class Program(models.Model):
    department = models.ForeignKey(
        Department,
        on_delete=models.CASCADE,
        related_name="programs"
    )
    name = models.CharField(max_length=200)
    code = models.CharField(max_length=20)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["department", "code"],
                name="unique_program_per_department"
            )
        ]
        indexes = [
            models.Index(fields=["code"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.code})"


class WorkingDay(models.Model):
    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name="working_days"
    )
    day = models.CharField(max_length=10)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["program", "day"],
                name="unique_working_day_per_program"
            )
        ]

    def __str__(self):
        return f"{self.program.code} - {self.day}"


class AcademicTerm(models.Model):
    program = models.ForeignKey(
        Program,
        on_delete=models.CASCADE,
        related_name="terms"
    )
    year = models.PositiveIntegerField()
    semester = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["program", "year", "semester"],
                name="unique_term_per_program"
            )
        ]
        indexes = [
            models.Index(fields=["program"]),
        ]

    def __str__(self):
        return f"{self.program.code} - Y{self.year} S{self.semester}"


# ----------------------------
# COURSE STRUCTURE
# ----------------------------

class CourseType(models.TextChoices):
    THEORY = "THEORY", "Theory"
    LAB = "LAB", "Lab"
    ELECTIVE = "ELECTIVE", "Elective"
    VAM = "VAM", "VAM"


class Course(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)

    course_type = models.CharField(
        max_length=20,
        choices=CourseType.choices,
        default=CourseType.THEORY
    )

    min_weekly_lectures = models.PositiveIntegerField()
    max_weekly_lectures = models.PositiveIntegerField()

    # Constraint Support
    priority = models.PositiveIntegerField(default=1)
    requires_lab_room = models.BooleanField(default=False)
    requires_consecutive_slots = models.BooleanField(default=False)

    class Meta:
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["course_type"]),
        ]

    def __str__(self):
        return f"{self.code} - {self.name}"


# ----------------------------
# STUDENT GROUPS
# ----------------------------

class StudentGroup(models.Model):
    term = models.ForeignKey(
        AcademicTerm,
        on_delete=models.CASCADE,
        related_name="student_groups"
    )
    name = models.CharField(max_length=50)
    description = models.CharField(max_length=150, blank=True)
    strength = models.PositiveIntegerField()

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["term", "name"],
                name="unique_group_per_term"
            )
        ]
        indexes = [
            models.Index(fields=["term"]),
        ]

    def __str__(self):
        return f"{self.term} - {self.name}"


# ----------------------------
# ROOM MANAGEMENT
# ----------------------------

class RoomType(models.TextChoices):
    THEORY = "THEORY", "Theory"
    LAB = "LAB", "Lab"


class Room(models.Model):
    name = models.CharField(max_length=50, unique=True)
    capacity = models.PositiveIntegerField()
    room_type = models.CharField(
        max_length=20,
        choices=RoomType.choices,
        default=RoomType.THEORY
    )

    class Meta:
        indexes = [
            models.Index(fields=["room_type"]),
        ]

    def __str__(self):
        return f"{self.name} ({self.room_type})"


# ----------------------------
# COURSE OFFERING (BRIDGE MODEL)
# ----------------------------

class CourseOffering(models.Model):
    course = models.ForeignKey(
        Course,
        on_delete=models.CASCADE,
        related_name="offerings"
    )
    student_group = models.ForeignKey(
        StudentGroup,
        on_delete=models.CASCADE,
        related_name="course_offerings"
    )

    assigned_faculty = models.ForeignKey(
        "faculty.Faculty",
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="course_assignments"
    )

    weekly_load = models.PositiveIntegerField(default=0)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["course", "student_group"],
                name="unique_course_per_group"
            )
        ]
        indexes = [
            models.Index(fields=["student_group"]),
            models.Index(fields=["assigned_faculty"]),
        ]

    def __str__(self):
        return f"{self.course.code} → {self.student_group}"


# ----------------------------
# TIMETABLE HISTORY (ML READY)
# ----------------------------

class TimetableVersion(models.Model):
    term = models.ForeignKey(
        AcademicTerm,
        on_delete=models.CASCADE,
        related_name="timetable_versions"
    )
    version_number = models.PositiveIntegerField(default=1)
    generated_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)

    class Meta:
        constraints = [
            models.UniqueConstraint(
                fields=["term", "version_number"],
                name="unique_version_per_term"
            )
        ]
        indexes = [
            models.Index(fields=["term"]),
        ]

    def __str__(self):
        return f"{self.term} - Version {self.version_number}"