<div align="center">

# ⏱️ TIMETRIX

### AI-Driven Constraint-Aware Academic Timetable Generation System

<br/>

![Python](https://img.shields.io/badge/Python_3.10+-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django_6.0-092E20?style=for-the-badge&logo=django&logoColor=white)
![React](https://img.shields.io/badge/React_19-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![Vite](https://img.shields.io/badge/Vite_7-646CFF?style=for-the-badge&logo=vite&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch_2.10-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn_1.8-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)

<br/>

*An intelligent, full-stack platform that automates university timetable scheduling using Graph Neural Networks, Random Forest prediction, and Constraint-Based Optimization — solving one of academia's hardest operational challenges.*

<br/>

---

</div>

## 🚀 Overview

**TIMETRIX** transforms the tedious, error-prone process of academic timetable creation into an automated, AI-powered workflow. Traditional manual scheduling is an **NP-hard combinatorial problem** involving hundreds of interacting variables:

| Entity | Constraints |
|:-------|:-----------|
| 👩‍🏫 **Faculty** | Availability windows, workload caps, subject eligibility, teaching preferences |
| 📚 **Courses** | Theory/Lab types, contact hours, consecutive slot requirements, parallel electives |
| 🧑‍🎓 **Student Sections** | Program, semester, group size, no double-booking |
| 🏫 **Rooms & Labs** | Capacity limits, type matching, building assignments |
| ⏰ **Time Slots** | Daily limits, lunch breaks, Saturday support |

TIMETRIX automates **80–90% of timetable creation** while respecting every constraint — producing conflict-free, balanced schedules in seconds.

---

## 📁 Project Structure

```
TIMETRIX/
│
├── 📂 client/                               # ⚛️  React 19 + Vite 7 Frontend
│   ├── public/
│   ├── src/
│   │   ├── 📂 api/
│   │   │   └── api.js                       #     Axios instance + interceptors
│   │   │
│   │   ├── 📂 components/                   #     Reusable UI components
│   │   │   ├── Sidebar.jsx                  #     Collapsible nav (mobile overlay)
│   │   │   ├── TopNavbar.jsx                #     Header bar (theme, notifications, user)
│   │   │   ├── BulkUploadCard.jsx           #     Excel upload with validation
│   │   │   ├── ProtectedRoute.jsx           #     Role-based route guard
│   │   │   ├── StatsSection.jsx             #     Dashboard stat cards
│   │   │   ├── TermStatusSection.jsx        #     Active term indicator
│   │   │   └── ActivitySection.jsx          #     Recent activity feed
│   │   │
│   │   ├── 📂 contexts/                     #     React Context providers
│   │   │   ├── AuthContext.jsx              #     Auth state (admin/teacher/student)
│   │   │   └── ThemeContext.jsx             #     Light / Dark theme toggle
│   │   │
│   │   ├── 📂 layouts/
│   │   │   └── DashboardLayout.jsx          #     Sidebar + Navbar shell
│   │   │
│   │   ├── 📂 pages/                        #     Full page views
│   │   │   ├── LoginPage.jsx                #     Animated login with role selection
│   │   │   ├── Dashboard.jsx                #     Overview stats + recent activity
│   │   │   ├── ProgramsPage.jsx             #     Program CRUD + bulk upload
│   │   │   ├── SectionsPage.jsx             #     Student group management
│   │   │   ├── FacultyPage.jsx              #     Faculty cards, eligibility, detail view
│   │   │   ├── CoursesPage.jsx              #     Course catalog by program
│   │   │   ├── CourseAssignmentPage.jsx     #     Course offering ↔ faculty binding
│   │   │   ├── FacultyEligibilityPage.jsx   #     Eligibility management
│   │   │   ├── InfrastructurePage.jsx       #     Buildings, rooms, labs
│   │   │   ├── TimetableGeneratorPage.jsx   #     Trigger + monitor schedule generation
│   │   │   ├── GeneratedTimetablesPage.jsx  #     Role-based timetable viewer
│   │   │   └── SettingsPage.jsx             #     Global scheduler configuration
│   │   │
│   │   ├── 📂 routes/
│   │   │   └── AppRoutes.jsx                #     Route definitions + guards
│   │   │
│   │   ├── 📂 styles/
│   │   │   └── global.css                   #     4700+ line design system
│   │   │
│   │   ├── 📂 utils/
│   │   │   └── helpers.js                   #     Shared utility functions
│   │   │
│   │   ├── App.jsx                          #     Root component
│   │   └── main.jsx                         #     Entry point
│   │
│   ├── index.html
│   ├── package.json
│   └── vite.config.js
│
├── 📂 server/                               # 🐍  Django 6.0 Backend
│   ├── manage.py
│   │
│   ├── 📂 config/                           #     Django project settings
│   │   ├── settings.py                      #     CORS, apps, DB, middleware
│   │   ├── urls.py                          #     Root URL routing (/api/...)
│   │   ├── asgi.py
│   │   └── wsgi.py
│   │
│   ├── 📂 academics/                        #     🎓 Academic domain
│   │   ├── models.py                        #     Department, Program, Course, Term, StudentGroup, CourseOffering
│   │   ├── serializers.py
│   │   ├── views.py                         #     CRUD + bulk upload endpoints
│   │   ├── urls.py
│   │   └── migrations/
│   │
│   ├── 📂 faculty/                          #     👩‍🏫 Faculty domain
│   │   ├── models.py                        #     Faculty, Availability, Eligibility, ProgramExclusion, SemesterExclusion
│   │   ├── serializers.py
│   │   ├── views.py                         #     CRUD + workload + bulk upload
│   │   ├── urls.py
│   │   └── migrations/
│   │
│   ├── 📂 infrastructure/                   #     🏫 Infrastructure domain
│   │   ├── models.py                        #     Building, Room, ProgramRoomMapping
│   │   ├── serializers.py
│   │   ├── views.py
│   │   ├── urls.py
│   │   └── migrations/
│   │
│   ├── 📂 scheduler/                        #     🤖 Scheduling engine
│   │   ├── models.py                        #     TimeSlot, Timetable, LectureAllocation, Notification, SchedulerConfig
│   │   ├── serializers.py
│   │   ├── views.py                         #     Generate, Schedule, Config, Notifications
│   │   ├── urls.py
│   │   ├── 📂 engine/                       #     ⚙️  Core scheduling logic
│   │   │   ├── runner.py                    #     Main SchedulerEngine (~1900 lines)
│   │   │   ├── constants.py                 #     Days, slots, valid pairs
│   │   │   ├── constraint_tracker.py        #     Real-time constraint monitoring
│   │   │   ├── difficulty.py                #     Course difficulty scoring
│   │   │   ├── feasibility.py               #     Pre-run feasibility checks
│   │   │   ├── ml_scorer.py                 #     ML model integration layer
│   │   │   └── observability.py             #     Logging + metrics
│   │   └── 📂 management/commands/          #     Django management commands
│   │
│   └── 📂 ml_pipeline/                      #     🧠 Machine Learning pipeline
│       ├── graph_builder.py                 #     Heterogeneous graph construction (NetworkX)
│       ├── gnn_model.py                     #     GraphSAGE training + embedding generation
│       ├── random_forest_model.py           #     RF slot predictor training
│       ├── visualize_embeddings.py          #     Embedding visualization + analysis
│       │
│       ├── 📂 data/                         #     📊 Training datasets (⚠️ gitignored)
│       │   ├── .gitkeep
│       │   ├── generate_templates.py        #     Template generator script
│       │   └── 📂 templates/               #     Blank Excel upload templates
│       │       ├── TIMETRIX_Programs_Template.xlsx
│       │       ├── TIMETRIX_Courses_Template.xlsx
│       │       ├── TIMETRIX_Faculty_Template.xlsx
│       │       ├── TIMETRIX_Rooms_Template.xlsx
│       │       └── TIMETRIX_CourseOfferings_Template.xlsx
│       │
│       └── 📂 trained/                      #     🏋️ Model artifacts (⚠️ gitignored)
│           └── .gitkeep
│
├── requirements.txt                         #     Python dependencies
├── .gitignore
└── README.md
```

---

## 🧠 Scheduling Architecture

TIMETRIX uses a **multi-stage hybrid AI + constraint solving pipeline**:

```
                    ┌─────────────────────────────────────────┐
                    │   Historical Timetable Data             │
                    │   1300+ rows · 22 features              │
                    └──────────────┬──────────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────────────┐
                    │   Feature Engineering & Cleaning        │
                    │   Normalize, encode, compute metrics    │
                    └──────────────┬──────────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────────────┐
                    │   Heterogeneous Graph Construction      │
                    │   5 node types · 7 edge types           │
                    └──────────────┬──────────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────────────┐
                    │   GraphSAGE GNN (2 layers · 32-dim)     │
                    │   Link prediction → node embeddings     │
                    └──────────────┬──────────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────────────┐
                    │   Random Forest Slot Predictor          │
                    │   96-dim embeddings + 15-dim features   │
                    │         → suitability score             │
                    └──────────────┬──────────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────────────┐
                    │   Constraint-Based Scheduler            │
                    │   Hard + soft constraint enforcement    │
                    └──────────────┬──────────────────────────┘
                                   │
                                   ▼
                    ┌─────────────────────────────────────────┐
                    │   ✅ Conflict-Free Timetable             │
                    └─────────────────────────────────────────┘
```

---

## ✨ Core Features

<table>
<tr>
<td width="50%">

### 📚 Academic Management
- Department → Program → Course hierarchy
- 12 course types (theory, lab, elective, life skills, etc.)
- Student sections with strength tracking
- Course offerings with faculty binding
- Bulk Excel upload for all entities

</td>
<td width="50%">

### 👩‍🏫 Faculty Management
- Role-based workload limits (Dean → Regular)
- **3-level exclusion system:**
  - 🔴 Program-level — block entire program
  - 🟠 Semester-level — block specific semester
  - 🟡 Course-level — block individual course
- Availability slot configuration
- Designation, department, teaching type

</td>
</tr>
<tr>
<td>

### 🏫 Infrastructure
- Buildings, classrooms, laboratories
- Room capacity, type, and floor tracking
- Program-room priority mapping
- Lab vs. classroom enforcement

</td>
<td>

### 🤖 Intelligent Scheduling
- Lab-first strategy with 2-slot enforcement
- ML-powered candidate ranking (GraphSAGE + RF)
- Heuristic fallback when ML unavailable
- Faculty workload balancing
- Conflict detection & prevention
- Lunch break protection

</td>
</tr>
<tr>
<td>

### 📊 Timetable Viewer
- **Section view** — program/semester/section grid
- **Faculty view** — full weekly schedule
- **Room view** — occupancy matrix
- Dynamic 15-color palette with legend
- Version history & PDF export
- Role-based access control

</td>
<td>

### ⚙️ Configuration & UX
- Global scheduler settings panel
- Auto-publish & notification triggers
- 🔔 In-app notification bell
- 🌙 Dark / Light theme
- 📱 Fully responsive (4 breakpoints)
- Mobile sidebar as overlay drawer

</td>
</tr>
</table>

---

## 🤖 Machine Learning Architecture

### 🕸️ Graph Neural Network — GraphSAGE

Scheduling data is modeled as a **heterogeneous graph**:

| Node Type | Dim | Features |
|:----------|:---:|:---------|
| **Faculty** | 8 | Designation, max hours, teaching type, breadth, employment |
| **Course** | 7 | Type, hours, lab flag, elective, semester, consecutive |
| **Section** | 5 | Program, semester, section ID, type, strength |
| **Room** | 6 | Lab flag, capacity, floor, type, shared |
| **TimeSlot** | 8 | Cyclic sin/cos encoding for time and day |

```
Faculty   ─── teaches ──────────► Course
Course    ─── belongs_to ────────► Section
Course    ─── scheduled_in ──────► TimeSlot
Course    ─── uses ──────────────► Room
Section   ─── occupied_at ───────► TimeSlot
Room      ─── occupied_at ───────► TimeSlot
Faculty   ─── available_at ──────► TimeSlot
```

The GNN produces **32-dimensional embeddings** via link prediction training.

---

### 🌲 Random Forest Slot Predictor

**Input: 111 dimensions** → **Output: Suitability score (0–1)**

```
 GNN Embeddings (96-dim)           Manual Features (15-dim)
 ┌──────────────────────┐          ┌─────────────────────────┐
 │ faculty_emb    (32)  │          │ load_remaining      (1) │
 │ timeslot_emb   (32)  │    +     │ fac_course_affinity (1) │
 │ room_emb       (32)  │          │ is_lab / morning    (1) │
 └──────────────────────┘          │ slot_popularity     (1) │
                                   │ ... 11 more features    │
                                   └─────────────────────────┘
                         ↓
            ┌────────────────────────┐
            │  Random Forest Model   │
            │  (VotingClassifier)    │
            └────────┬───────────────┘
                     ↓
    Tue 10:35 → 0.86 ✅    Fri 09:40 → 0.21 ❌
```

---

### ⚙️ Constraint Engine

| Type | Rule |
|:-----|:-----|
| 🔴 **Hard** | No double-booking (faculty / room / group) |
| 🔴 **Hard** | Labs must occupy 2 consecutive slots |
| 🔴 **Hard** | Faculty weekly workload limits (role-based) |
| 🔴 **Hard** | Lunch break protection |
| 🟢 **Soft** | Faculty time preferences & availability |
| 🟢 **Soft** | Room-course affinity matching |
| 🟢 **Soft** | Balanced workload distribution |

---

## 🧱 Tech Stack

<table>
<tr>
<td align="center" width="25%">

**Backend**

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django_6.0-092E20?logo=django&logoColor=white)
![DRF](https://img.shields.io/badge/DRF_3.16-red)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)

</td>
<td align="center" width="25%">

**Frontend**

![React](https://img.shields.io/badge/React_19-20232A?logo=react&logoColor=61DAFB)
![Vite](https://img.shields.io/badge/Vite_7-646CFF?logo=vite&logoColor=white)
![Router](https://img.shields.io/badge/Router_7-CA4245?logo=react-router&logoColor=white)
![Axios](https://img.shields.io/badge/Axios-5A29E4?logo=axios&logoColor=white)

</td>
<td align="center" width="25%">

**Machine Learning**

![PyTorch](https://img.shields.io/badge/PyTorch_2.10-EE4C2C?logo=pytorch&logoColor=white)
![PyG](https://img.shields.io/badge/PyG_2.7-orange)
![sklearn](https://img.shields.io/badge/sklearn_1.8-F7931E?logo=scikit-learn&logoColor=white)

</td>
<td align="center" width="25%">

**Data & Viz**

![Pandas](https://img.shields.io/badge/Pandas-150458?logo=pandas&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy-013243?logo=numpy&logoColor=white)
![NetworkX](https://img.shields.io/badge/NetworkX-black)

</td>
</tr>
</table>

---

## 🌐 API Reference

<details>
<summary><b>📚 Academics</b> — <code>/api/academics/</code></summary>

| Endpoint | Methods | Description |
|:---------|:--------|:------------|
| `departments/` | CRUD | Department management |
| `programs/` | CRUD | Program management |
| `terms/` | CRUD | Academic terms |
| `courses/` | CRUD | Course catalog |
| `student-groups/` | CRUD | Section management |
| `course-offerings/` | CRUD | Course ↔ faculty binding |
| `programs/bulk-upload/` | POST | Excel bulk import |
| `courses/bulk-upload/` | POST | Excel bulk import |

</details>

<details>
<summary><b>👩‍🏫 Faculty</b> — <code>/api/faculty/</code></summary>

| Endpoint | Methods | Description |
|:---------|:--------|:------------|
| `faculty/` | CRUD | Faculty profiles |
| `teacher-availability/` | CRUD | Availability windows |
| `faculty-subject-eligibility/` | CRUD | Course exclusions |
| `program-exclusions/` | CRUD | Program-level exclusions |
| `semester-exclusions/` | CRUD | Semester-level exclusions |
| `faculty/bulk-upload/` | POST | Excel bulk import |
| `faculty/workload/` | GET | Workload summary |

</details>

<details>
<summary><b>🏫 Infrastructure</b> — <code>/api/infrastructure/</code></summary>

| Endpoint | Methods | Description |
|:---------|:--------|:------------|
| `building/` | CRUD | Building management |
| `room/` | CRUD | Rooms and labs |
| `program-room-map/` | CRUD | Room priority per program |

</details>

<details>
<summary><b>🤖 Scheduler</b> — <code>/api/scheduler/</code></summary>

| Endpoint | Methods | Description |
|:---------|:--------|:------------|
| `timeslots/` | CRUD | Time slot definitions |
| `timetables/` | CRUD | Timetable versions |
| `allocations/` | CRUD | Lecture slot allocations |
| `generate/` | POST | Trigger timetable generation |
| `schedule/` | GET | Enriched schedule view |
| `config/` | GET · PUT · PATCH | Global scheduler settings |
| `notifications/` | GET · PATCH · DELETE | In-app notifications |
| `notifications/mark-all-read/` | PATCH | Bulk mark read |

**Schedule View Query Parameters:**

| `view` | Required Param | Returns |
|:-------|:--------------|:--------|
| `section` | `student_group_id` | Section weekly timetable |
| `faculty` | `faculty_id` | Faculty weekly schedule |
| `room` | `room_id` | Room occupancy grid |

</details>

---

## ⚙️ Installation & Setup

### Prerequisites

- **Python** 3.10+
- **Node.js** 18+
- **pip** (Python package manager)

### 1️⃣ Clone the Repository

```bash
git clone https://github.com/Akki-06/timetrix.git
cd timetrix
```

### 2️⃣ Backend Setup

```bash
# Create and activate virtual environment
python -m venv venv

# Windows
venv\Scripts\activate
# macOS / Linux
source venv/bin/activate

# Install dependencies
pip install -r requirements.txt

# Run migrations
cd server
python manage.py makemigrations
python manage.py migrate

# Start the backend server
python manage.py runserver
```

> Backend runs at → `http://127.0.0.1:8000`

### 3️⃣ Frontend Setup

```bash
cd client
npm install
npm run dev
```

> Frontend runs at → `http://localhost:5173`

### 4️⃣ Demo Login

| Role | Username | Password |
|:-----|:---------|:---------|
| 🔑 Admin | `admin` | `admin123` |
| 👩‍🏫 Teacher | `teacher` | `teacher123` |
| 🧑‍🎓 Student | `student` | `student123` |

### 5️⃣ ML Pipeline (Optional)

Pre-trained models are not included in the repo (gitignored due to size). To train from scratch:

```bash
cd server

# Step 1: Build heterogeneous graph from dataset
python manage.py build_graph

# Step 2: Train GraphSAGE GNN (generates node embeddings)
python ml_pipeline/gnn_model.py

# Step 3: Train Random Forest slot predictor
python ml_pipeline/random_forest_model.py
```

> ⚠️ Training requires the dataset files in `server/ml_pipeline/data/`. Contact the author for sample data.

---

## 📊 Dataset

TIMETRIX trains on **historical timetable records** from a real university:

```
Records:   1,300+
Features:  22
```

| Field | Description |
|:------|:-----------|
| `academic_year` | Year of the record |
| `semester_type` | Odd / Even |
| `program` | Degree program |
| `semester` | 1–8 |
| `course_code` | Unique course identifier |
| `faculty` | Assigned faculty name |
| `room` | Room allocated |
| `day` / `slot_index` | Scheduled day and time slot |
| `session_type` | Theory / Lab |
| `contact_hours_weekly` | Teaching load |

> ⚠️ Raw dataset files are **gitignored** for data privacy. Only blank upload templates are included.

---

## 📊 Status & Roadmap

### ✅ Completed

- [x] Full Django REST backend — 4 apps, 20+ models, complete CRUD APIs
- [x] Modern React 19 frontend — 12 pages, glassmorphism design, dark/light theme
- [x] Demo auth with role-based route guards (Admin / Teacher / Student)
- [x] Heterogeneous graph — 5 node types, 7 edge types (NetworkX)
- [x] GraphSAGE GNN — 32-dim embeddings via link prediction
- [x] Random Forest slot predictor — 111-dim input, VotingClassifier ensemble
- [x] Constraint-based scheduler with ML integration + heuristic fallback
- [x] Lab-first scheduling with consecutive 2-slot enforcement
- [x] Parallel elective support
- [x] 3-level faculty exclusion system (program → semester → course)
- [x] Faculty detail view with workload stats + eligibility breakdown
- [x] Sortable faculty list (name, designation, workload)
- [x] Bulk Excel upload for Programs, Courses, Faculty, Rooms
- [x] Timetable version management with auto-pruning
- [x] Role-based timetable views (Section / Faculty / Room)
- [x] Dynamic color-coded timetable grid with legend
- [x] In-app notifications with bell icon
- [x] Auto-publish on generation
- [x] Global scheduler settings panel
- [x] Responsive UI — mobile sidebar, 4 breakpoints

### 🔮 Future Enhancements

- [ ] Reinforcement learning optimization
- [ ] Genetic algorithm fallback scheduler
- [ ] Docker containerization
- [ ] PostgreSQL production database
- [ ] Real JWT authentication with user linkage
- [ ] Multi-institution / multi-campus support
- [ ] iCal / Google Calendar export
- [ ] Advanced analytics dashboard

---

## 👨‍💻 Author

**Akhil**
BCA Student · Full-Stack Developer · AI Systems Enthusiast

---

<div align="center">

*Developed for academic and educational purposes.*

<br/>

![Made with ❤️](https://img.shields.io/badge/Made_with-❤️-red?style=flat-square)
![Status](https://img.shields.io/badge/Status-Active-success?style=flat-square)

</div>
