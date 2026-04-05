import pandas as pd
import os
from pathlib import Path

def create_templates():
    base_dir = Path(__file__).resolve().parent / "templates"
    base_dir.mkdir(parents=True, exist_ok=True)

    # 1. Programs & Specializations Template
    programs_df = pd.DataFrame([
        {"Program Name": "Bachelor of Computer Applications", "Program Code": "BCA", "Specialization": "Data Science", "Core Program": "BCA"},
        {"Program Name": "Bachelor of Computer Applications", "Program Code": "BCA", "Specialization": "Cyber Security", "Core Program": "BCA"},
        {"Program Name": "Bachelor of Technology", "Program Code": "BTech", "Specialization": "CSE", "Core Program": "BTech"}
    ])
    programs_df.to_excel(base_dir / "TIMETRIX_Programs_Template.xlsx", index=False)

    # 2. Courses Master Template
    courses_df = pd.DataFrame([
        {"Course Code": "BCA101", "Course Name": "Programming in C", "Course Type": "Core", "Program": "BCA", "Semester": 1, "Contact Hours (Theory)": 3, "Contact Hours (Lab)": 2, "Is Lab Required?": "Yes"},
        {"Course Code": "BCA402", "Course Name": "Database Management System", "Course Type": "Core", "Program": "BCA", "Semester": 4, "Contact Hours (Theory)": 4, "Contact Hours (Lab)": 0, "Is Lab Required?": "No"}
    ])
    courses_df.to_excel(base_dir / "TIMETRIX_Courses_Template.xlsx", index=False)

    # 3. Faculty Template
    faculty_df = pd.DataFrame([
        {"Faculty Name": "Dr. Rahul Bhatt", "Employee ID": "EMP001", "Role": "Regular Faculty", "Department": "Computer Science", "Max Lectures/Day": 4, "Max Weekly Load": 18},
        {"Faculty Name": "Ms. Manvi Chopra", "Employee ID": "EMP002", "Role": "HOD", "Department": "Information Technology", "Max Lectures/Day": 3, "Max Weekly Load": 12}
    ])
    faculty_df.to_excel(base_dir / "TIMETRIX_Faculty_Template.xlsx", index=False)

    # 4. Rooms Template
    rooms_df = pd.DataFrame([
        {"Building": "Block A", "Room Number": "1118", "Floor": 1, "Room Type": "Theory Classroom", "Capacity": 60, "Is Shared": "Yes"},
        {"Building": "Block B", "Room Number": "Lab 1", "Floor": 2, "Room Type": "Laboratory", "Capacity": 30, "Is Shared": "No"}
    ])
    rooms_df.to_excel(base_dir / "TIMETRIX_Rooms_Template.xlsx", index=False)

    # 5. Course Offerings (Load Distribution) Template
    # This is the most complex one. 
    # Must support Section (A, B, C) and Combined Sections (A+B, B+C) logic.
    offerings_df = pd.DataFrame([
        {"Day": "", "Slot": "", "Program": "BCA", "Specialization": "Data Science", "Sem": 4, "Section": "A", "Course Name": "Machine Learning", "Course Code": "BCA405", "Faculty Name": "Dr. Rahul Bhatt", "Theory/Lab": "Theory", "Room": "1118"},
        {"Day": "", "Slot": "", "Program": "BCA", "Specialization": "Cyber Security", "Sem": 4, "Section": "B", "Course Name": "Machine Learning", "Course Code": "BCA405", "Faculty Name": "Dr. Rahul Bhatt", "Theory/Lab": "Theory", "Room": "1118"},
        {"Day": "", "Slot": "", "Program": "BCA", "Specialization": "Core", "Sem": 4, "Section": "C", "Course Name": "AEC", "Course Code": "AEC01", "Faculty Name": "Harpreet Singh Cheema", "Theory/Lab": "Theory", "Room": "1120"}
    ])
    offerings_df.to_excel(base_dir / "TIMETRIX_CourseOfferings_Template.xlsx", index=False)

    print(f"Created 5 templates in {base_dir}")

if __name__ == "__main__":
    create_templates()
