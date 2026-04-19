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
    name = models.CharField(max_length=100)
    code = models.CharField(max_length=50, unique=True)
    specialization = models.CharField(max_length=150, blank=True, default="")
    short_form = models.CharField(
        max_length=20, blank=True, default="",
        help_text="Short abbreviation e.g. BTCSE, BCAFSD — used for internal suffixes and compact displays"
    )
    total_years = models.PositiveIntegerField(default=4)
    total_semesters = models.PositiveIntegerField(default=8)

    class Meta:
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["department"]),
        ]

    @property
    def display_name(self):
        if self.specialization:
            return f"{self.name} ({self.specialization})"
        return self.name

    def __str__(self):
        return self.display_name


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
    # Schedulable: theory-style, credit-mapped
    PC  = "PC",  "Program Core"
    PE  = "PE",  "Program Elective"
    OE  = "OE",  "Open Elective"
    BSC = "BSC", "Basic Sciences Course"
    ESC = "ESC", "Engineering Sciences Course"
    HUM = "HUM", "Humanities"
    # Schedulable: fixed 1 slot regardless of credits
    LS  = "LS",  "Life Skills"
    VAM = "VAM", "Value Added Module"
    AEC = "AEC", "Ability Enhancement Course"
    # Schedulable: lab (2 consecutive slots, lab room required)
    PR  = "PR",  "Practical (Lab)"
    # Not schedulable: self-directed / off-campus
    PRJ = "PRJ", "Project"
    DIS = "DIS", "Dissertation"
    INT = "INT", "Internship"
    RND = "RND", "Research"


_NOT_SCHEDULED     = {"DIS", "INT", "RND"}
_CONSECUTIVE_TYPES = {"PR", "PRJ"}
_LAB_ROOM_TYPES    = {"PR"}
_TYPE_PRIORITY = {
    "PR": 5,
    "PC": 4, "BSC": 4, "ESC": 4,
    "PE": 3, "OE": 3, "HUM": 3,
    "LS": 2, "VAM": 2, "AEC": 2,
}


class Course(models.Model):
    code = models.CharField(max_length=50, unique=True)
    name = models.CharField(max_length=150)
    credits = models.PositiveIntegerField(default=3)

    program = models.ForeignKey(
        Program,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="courses"
    )
    semester = models.PositiveIntegerField(null=True, blank=True)

    course_type = models.CharField(
        max_length=20,
        choices=CourseType.choices,
        default=CourseType.PC
    )
    
    parent_course_code = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        help_text="If this is an elective choice, the code of the placeholder course (e.g. PE-I)"
    )

    min_weekly_lectures = models.PositiveIntegerField(default=0)
    max_weekly_lectures = models.PositiveIntegerField(default=0)

    # Constraint Support
    priority = models.PositiveIntegerField(default=1)
    requires_lab_room = models.BooleanField(default=False)
    requires_consecutive_slots = models.BooleanField(default=False)

    def save(self, *args, **kwargs):
        ct = self.course_type
        if ct in _CONSECUTIVE_TYPES:
            lectures = 1
        elif ct in _NOT_SCHEDULED:
            lectures = 0
        else:
            lectures = min(self.credits, 4)

        self.min_weekly_lectures        = lectures
        self.max_weekly_lectures        = lectures
        self.requires_lab_room          = (ct in _LAB_ROOM_TYPES)
        self.requires_consecutive_slots = (ct in _CONSECUTIVE_TYPES)

        self.priority = _TYPE_PRIORITY.get(ct, 1)

        super().save(*args, **kwargs)

    class Meta:
        indexes = [
            models.Index(fields=["code"]),
            models.Index(fields=["course_type"]),
        ]

    # Known internal suffixes added for DB uniqueness when same base code
    # appears in multiple programs. Stripped for display only.
    _DISPLAY_SUFFIXES = (
        "_BTCSCS", "_BTAIML",            # BTech CSE specializations (longer first)
        "_BCAFSD", "_BCACS",             # BCA specializations
        "_BSCIT",  "_BTCSE", "_BTCVL",  # UG programs
        "_BTAE",   "_BTECE", "_BTEE",
        "_BTME",   "_BTDS",
        "_MTGEO",  "_MTSTR", "_MTTRN",  # MTech programs
        "_MTCSE",  "_MTME",  "_MTDC",
        "_MTSG",
        "_BCA",    "_MCA",               # PG / remaining
    )

    @property
    def display_code(self) -> str:
        """Return the human-readable course code with internal program suffix stripped."""
        c = self.code
        for sfx in self._DISPLAY_SUFFIXES:
            if c.upper().endswith(sfx.upper()):
                return c[: -len(sfx)]
        return c

    def __str__(self):
        return f"{self.display_code} - {self.name}"


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
    working_days = models.JSONField(
        default=list, 
        blank=True,
        help_text='List of working days for this section, e.g. ["MON", "TUE", "WED", "THU", "FRI", "SAT"]'
    )

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
    
    # NEW: Used to group offerings that must be scheduled in the same slot 
    # (e.g. Sections A & B combined for one theory class)
    combined_token = models.CharField(max_length=50, blank=True, null=True, help_text="Common token for linked sessions (A+B)")

    elective_slot_group = models.CharField(
        max_length=50,
        null=True,
        blank=True,
        db_index=True,
        help_text=(
            "Offerings sharing this value are forced to the same "
            "day+slot with different rooms. Used for parallel PE electives."
        )
    )

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