from django.db import models


class Department(models.Model):
    name = models.CharField(max_length=100, unique=True)
    code = models.CharField(max_length=20, unique=True)
    
    def __str__(self):
        return self.name
    
    
class Program(models.Model):
    department = models.ForeignKey(Department, on_delete=models.CASCADE, related_name="programs")
    name = models.CharField(max_length=200, unique=True)
    code = models.CharField(max_length=20, unique=True)
    
    # Working days (program-specific)
    monday = models.BooleanField(default=True)
    tuesday = models.BooleanField(default=True)
    wednesday = models.BooleanField(default=True)
    thursday = models.BooleanField(default=True)
    friday = models.BooleanField(default=True)
    saturday = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.name} : {self.code}"
    
    
class AcademicTerm(models.Model):
    program = models.ForeignKey(Program, on_delete=models.CASCADE, related_name="terms")
    year = models.PositiveIntegerField()
    semester = models.PositiveIntegerField()
    
    class Meta:
        unique_together = ("program", "year", "semester")
        
    def __str__(self):
        return f"{self.program.code} - Y{self.year} S{self.semester}"
    
    
class Courses(models.Model):
    code = models.CharField(max_length=20, unique=True)
    name = models.CharField(max_length=150)
    weekly_lectures = models.PositiveIntegerField()
    is_lab = models.BooleanField(default=False)
    
    def __str__(self):
        return f"{self.code} - {self.name}"
    
    
class StudentGroup(models.Model):
    term = models.ForeignKey(AcademicTerm, on_delete=models.CASCADE, related_name="student_groups")
    name = models.CharField(max_length=50)
    description = models.CharField(max_length=150, blank=True)
    
    def __str__(self):
        return f"{self.term} - {self.name}"
    


class CourseOffering(models.Model):
    course = models.ForeignKey(Courses, on_delete=models.CASCADE, related_name="offerings")
    student_group = models.ForeignKey(StudentGroup, on_delete=models.CASCADE, related_name="course_offerings")

    def __str__(self):
        return f"{self.course.code} → {self.student_group}"
