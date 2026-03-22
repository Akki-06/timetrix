# ⏱️ TIMETRIX
### 🧠 AI-Driven Constraint-Aware Academic Timetable Generation System

<div align="center">

![Python](https://img.shields.io/badge/Python-3776AB?style=for-the-badge&logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django_6.0-092E20?style=for-the-badge&logo=django&logoColor=white)
![React](https://img.shields.io/badge/React_19-20232A?style=for-the-badge&logo=react&logoColor=61DAFB)
![Vite](https://img.shields.io/badge/Vite_7-646CFF?style=for-the-badge&logo=vite&logoColor=white)
![PyTorch](https://img.shields.io/badge/PyTorch_2.10-EE4C2C?style=for-the-badge&logo=pytorch&logoColor=white)
![scikit-learn](https://img.shields.io/badge/scikit--learn_1.8-F7931E?style=for-the-badge&logo=scikit-learn&logoColor=white)

</div>

---

## 🚀 Overview

**TIMETRIX** is an intelligent academic timetable generation platform that automates university scheduling using a hybrid approach of **Graph Neural Networks, Random Forest Prediction, and Constraint-based Optimization**.

Timetable scheduling is a **complex NP-hard problem** involving multiple interacting entities:

| Entity | Role |
|--------|------|
| 👩‍🏫 Faculty | Availability, workload limits, subject eligibility |
| 📚 Courses | Theory/Lab, contact hours, priority |
| 🧑‍🎓 Student Sections | Groups, program, semester |
| 🏫 Rooms & Labs | Capacity, type, building |
| ⏰ Time Slots | Days, slots, lunch breaks |

Manual scheduling leads to conflicts, inefficient resource usage, and heavy administrative overhead. TIMETRIX automates **80–90% of timetable creation** while respecting all academic constraints.

---

## 🧠 Scheduling Architecture

TIMETRIX uses a **multi-stage hybrid AI + constraint solving pipeline**:

```
 Historical Timetable Data  (1300+ rows, 22 features)
            ↓
 Dataset Cleaning & Feature Engineering
            ↓
 Heterogeneous Graph Construction  (NetworkX)
            ↓
 Graph Neural Network — GraphSAGE  (2 layers, 32-dim embeddings)
            ↓
 Node Embeddings  (faculty + course + section → 96-dim concat)
            ↓
 Random Forest Slot Predictor  (111-dim input → suitability score)
            ↓
 Constraint-Based Scheduler  (hard + soft constraints)
            ↓
 ✅ Final Conflict-Free Timetable
```

---

## ✨ Core Features

### 📚 Academic Management
- Departments, Programs, Academic Terms
- Course definitions (12 types: theory, lab, elective, life skills, etc.)
- Student sections with strength and program mapping
- Course offerings with faculty assignment and weekly load

### 👩‍🏫 Faculty Management
- Faculty profiles with role-based workload limits

  | Role | Max Weekly Hours |
  |------|-----------------|
  | Dean | 6 hrs |
  | HOD | 12 hrs |
  | Senior | 16 hrs |
  | Regular | 18 hrs |
  | Visiting | 18 hrs |

- Subject eligibility with priority weights
- Availability slots (day/time window configuration)
- Bulk upload via Excel (`.xlsx`)

### 🏫 Infrastructure Management
- Buildings, classrooms, laboratories
- Room capacity, type, and floor tracking
- Program-room priority mapping

### 🤖 Intelligent Scheduling
- **Lab-first strategy** — schedule labs before theory (limited lab rooms)
- **Consecutive slot enforcement** — lab sessions span 2 contiguous slots
- **Faculty workload balancing** — role-based hour limits respected
- **Conflict detection** — faculty / room / group double-booking prevention
- **ML-based candidate ranking** — RF scores all (faculty, room, day, slot) combos
- **Graceful degradation** — heuristic fallback if ML models unavailable
- **Lunch break protection** — enforced across all sections
- **Saturday support** — configurable weekend classes
- **Version management** — multiple timetable versions per term; auto-pruning of history
- **Auto-publish** — optional finalization on generation
- **In-app notifications** — generation success/failure alerts with bell icon

### 📊 Timetable Viewing — Role-Based
The `/timetables` page adapts its available views by logged-in role:

| Role | Available Views |
|------|----------------|
| **Admin** | Program/Section · Faculty Schedule · Room Occupancy |
| **Teacher** | Faculty Schedule · Program/Section |
| **Student** | Program/Section |

- **Program/Section view** — select Program → Semester → Section; shows color-coded weekly grid
- **Faculty view** — select any faculty; shows their full weekly schedule across all programs
- **Room view** — select any room; shows which group/faculty occupies each slot
- **Dynamic color palette** — 15 distinct colors auto-assigned per course; legend shown below grid
- **Version selector** — admins can view older timetable versions (not just latest)
- **PDF export** via browser print

### ⚙️ Scheduler Configuration
A global settings panel (admin only) controls:
- Faculty hour caps per role
- Max lectures per day and consecutive lecture limits
- Allow/deny weekend classes (Saturday)
- Enforce room type matching
- Auto-publish on generation
- Notification preferences
- Timetable history retention limit

### 📱 Responsive UI
- Mobile-first layout with 4 breakpoints (1200px, 900px, 768px, 480px)
- Sidebar collapses to icon strip on desktop; slides in as overlay drawer on mobile
- Light / dark theme toggle

---

## 🤖 Machine Learning Architecture

### 🕸️ Graph Neural Network — GraphSAGE

Scheduling data is modeled as a **heterogeneous graph** where each entity is a typed node:

#### Node Types & Feature Dimensions

| Node Type | Feature Dim | Key Features |
|-----------|-------------|-------------|
| Faculty | 8-dim | Designation, max hours, teaching type, breadth, employment, roles |
| Course | 7-dim | Type, hours, lab flag, elective, semester, program, consecutive |
| Section | 5-dim | Program, semester, section ID, type, strength |
| Room | 6-dim | Lab flag, capacity, floor, type, lab-type, shared |
| TimeSlot | 8-dim | Cyclic time encoding (sin/cos for time and day) |

#### Graph Relationships (Edges)

```
Faculty   ──── teaches ────────► Course
Course    ──── belongs_to ──────► Section
Course    ──── scheduled_in ────► TimeSlot
Course    ──── uses ────────────► Room
Section   ──── occupied_at ─────► TimeSlot
Room      ──── occupied_at ─────► TimeSlot
Faculty   ──── available_at ────► TimeSlot
```

**Frameworks:** PyTorch 2.10 · PyTorch Geometric 2.7 · NetworkX 3.6

The GNN is trained via **link prediction** (real edges vs. 7-type negative samples) and produces **32-dimensional node embeddings** that capture hidden scheduling patterns.

---

### 🌲 Random Forest Slot Predictor

The RF model ranks scheduling candidates by **slot suitability probability**.

#### Input Features — 111 Dimensions Total

```
faculty_embedding   (32-dim)  ─┐
timeslot_embedding  (32-dim)   ├─ GNN embeddings (96-dim)
room_embedding      (32-dim)  ─┘
+
load_remaining         (1)    ─┐
is_known_slot          (1)     │
fac_course_affinity    (1)     │
slot_popularity        (1)     │
day_popularity         (1)     │ Manual features (15-dim)
is_lab                 (1)     │
is_consecutive_lab     (1)     │
is_morning             (1)     │
is_post_lunch          (1)     │
semester_norm          (1)     │
contact_norm           (1)     │
breadth_norm           (1)     │
fac_today_ratio        (1)     │
slot_adjacent_density  (1)     │
near_weekly_cap        (1)    ─┘
```

#### Output — Suitability Score

```
Tue 10:35  →  0.86  ✅ High suitability
Wed 11:30  →  0.72  ✅ Good
Fri 09:40  →  0.21  ❌ Poor fit
```

Candidates are ranked by score before being validated against hard constraints.

#### ML Bug Fixes (resolved)
- **Day-string mismatch**: Training data stored days as `"Monday"`; scheduler passed `"MON"`. Fixed via `DAY_FULL` mapping applied consistently to `is_known_slot` and `day_popularity` features.
- **Saturday support**: `TimeSlot.DayChoices` extended with `SAT` so weekend scheduling config works end-to-end.

---

### ⚙️ Constraint-Based Scheduler

ML predictions are validated against strict scheduling rules:

#### Hard Constraints (Never Violated)
- Teacher cannot teach two classes simultaneously
- Room cannot host two classes simultaneously
- Lab sessions must occupy exactly 2 consecutive slots
- Faculty weekly workload limits (role-based)
- Lunch break protection

#### Soft Constraints (Optimized)
- Faculty time preferences and availability windows
- Affinity-based room-course matching
- Workload distribution across the week

The scheduler selects the **highest-ranked ML candidate** that satisfies all hard constraints. If no ML candidate is available, a heuristic fallback activates.

---

## 📊 Dataset

TIMETRIX trains on **historical timetable records from the university**:

```
Rows:     1300+
Features: 22
```

Key dataset fields:

| Field | Description |
|-------|-------------|
| `academic_year` | Year of the record |
| `semester_type` | Odd / Even |
| `program` | Degree program |
| `semester` | 1–8 |
| `section` | Student section |
| `course_code` | Unique course identifier |
| `faculty` | Assigned faculty name |
| `room` | Room allocated |
| `day` / `day_index` | Scheduled day |
| `slot_index` | Time slot position |
| `session_type` | Theory / Lab |
| `is_lab` | Boolean lab flag |
| `contact_hours_weekly` | Teaching load |

Each row represents a **single historical scheduling decision** used to train the ML pipeline.

---

## 🧱 Tech Stack

### Backend
![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django_6.0-092E20?logo=django&logoColor=white)
![DRF](https://img.shields.io/badge/Django_REST_Framework_3.16-red)
![CORS](https://img.shields.io/badge/django--cors--headers-blue)
![SQLite](https://img.shields.io/badge/SQLite-003B57?logo=sqlite&logoColor=white)

### Frontend
![React](https://img.shields.io/badge/React_19-20232A?logo=react&logoColor=61DAFB)
![Vite](https://img.shields.io/badge/Vite_7-646CFF?logo=vite&logoColor=white)
![React Router](https://img.shields.io/badge/React_Router_7-CA4245?logo=react-router&logoColor=white)
![Axios](https://img.shields.io/badge/Axios-5A29E4?logo=axios&logoColor=white)
![xlsx](https://img.shields.io/badge/xlsx-Export-green)

### Machine Learning
![PyTorch](https://img.shields.io/badge/PyTorch_2.10-EE4C2C?logo=pytorch&logoColor=white)
![PyG](https://img.shields.io/badge/PyTorch_Geometric_2.7-orange)
![scikit-learn](https://img.shields.io/badge/scikit--learn_1.8-F7931E?logo=scikit-learn&logoColor=white)
![NetworkX](https://img.shields.io/badge/NetworkX_3.6-black)

### Data Processing
![Pandas](https://img.shields.io/badge/Pandas_3.0-150458?logo=pandas&logoColor=white)
![NumPy](https://img.shields.io/badge/NumPy_2.4-013243?logo=numpy&logoColor=white)
![Matplotlib](https://img.shields.io/badge/Matplotlib_3.10-11557C)

---

## 📁 Project Structure

```
TIMETRIX/
│
├── client/                          # React + Vite frontend
│   ├── src/
│   │   ├── api/                     # Axios API service layer
│   │   ├── components/              # Reusable UI components
│   │   │   ├── Sidebar.jsx          # Collapsible nav (mobile overlay)
│   │   │   ├── TopNavbar.jsx        # Header with theme, notifications, user
│   │   │   ├── BulkUploadCard.jsx
│   │   │   ├── StatsSection.jsx
│   │   │   ├── ActivitySection.jsx
│   │   │   └── TermStatusSection.jsx
│   │   ├── contexts/
│   │   │   ├── AuthContext.jsx      # Demo auth (admin / teacher / student)
│   │   │   └── ThemeContext.jsx     # Light / dark theme
│   │   ├── layouts/
│   │   │   └── DashboardLayout.jsx  # Sidebar + navbar shell
│   │   ├── pages/
│   │   │   ├── LoginPage.jsx
│   │   │   ├── Dashboard.jsx
│   │   │   ├── ProgramsPage.jsx
│   │   │   ├── SectionsPage.jsx
│   │   │   ├── FacultyPage.jsx
│   │   │   ├── CoursesPage.jsx
│   │   │   ├── InfrastructurePage.jsx
│   │   │   ├── TimetableGeneratorPage.jsx
│   │   │   ├── GeneratedTimetablesPage.jsx  # Role-based views
│   │   │   └── SettingsPage.jsx
│   │   ├── routes/AppRoutes.jsx     # Role-guarded routes
│   │   ├── styles/global.css        # Single responsive stylesheet
│   │   └── utils/helpers.js
│   ├── package.json
│   └── vite.config.js
│
├── server/                          # Django backend
│   ├── manage.py
│   ├── config/                      # Django configuration
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── asgi.py
│   │   └── wsgi.py
│   ├── academics/                   # Departments, Programs, Courses, Terms, Groups
│   ├── faculty/                     # Faculty profiles, availability, eligibility
│   ├── infrastructure/              # Buildings, rooms, program-room mapping
│   ├── scheduler/                   # Scheduling engine + API
│   │   ├── scheduler_engine.py      # ML-integrated scheduling logic
│   │   ├── models.py                # TimeSlot, Timetable, LectureAllocation, Notification
│   │   ├── serializers.py
│   │   ├── views.py                 # Generate, Schedule, Config, Notifications
│   │   └── urls.py
│   └── ml_pipeline/                 # Machine learning pipeline
│       ├── data/                    # Training datasets (gitignored)
│       ├── trained/                 # Saved model artifacts (gitignored)
│       │   ├── gnn_model.pt             # GraphSAGE weights
│       │   ├── rf_model.pkl             # Random Forest classifier
│       │   ├── node_embeddings.pkl      # 32-dim node embeddings
│       │   ├── timetrix_graph.gpickle   # NetworkX graph
│       │   └── rf_feature_metadata.pkl  # Scaler + feature info
│       ├── graph_builder.py         # Heterogeneous graph construction
│       ├── gnn_model.py             # GraphSAGE implementation
│       ├── random_forest_model.py   # RF predictor v2
│       └── visualize_embeddings.py  # Embedding visualization
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

## 🌐 API Endpoints

### Academics
| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/api/academics/departments/` | CRUD | Department management |
| `/api/academics/programs/` | CRUD | Program management |
| `/api/academics/terms/` | CRUD | Academic terms |
| `/api/academics/courses/` | CRUD | Course catalog |
| `/api/academics/student-groups/` | CRUD | Section management |
| `/api/academics/course-offerings/` | CRUD | Course-section-faculty binding |

### Faculty
| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/api/faculty/faculty/` | CRUD | Faculty profiles |
| `/api/faculty/availability/` | CRUD | Availability windows |
| `/api/faculty/eligibility/` | CRUD | Subject eligibility |

### Infrastructure
| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/api/infrastructure/building/` | CRUD | Buildings |
| `/api/infrastructure/room/` | CRUD | Rooms and labs |
| `/api/infrastructure/program-room-map/` | CRUD | Room priority per program |

### Scheduler
| Endpoint | Methods | Description |
|----------|---------|-------------|
| `/api/scheduler/timeslots/` | CRUD | Time slot definitions |
| `/api/scheduler/timetables/` | CRUD | Timetable versions |
| `/api/scheduler/allocations/` | CRUD | Individual lecture slots |
| `/api/scheduler/generate/` | POST | Trigger timetable generation |
| `/api/scheduler/schedule/` | GET | Enriched view (section / faculty / room) |
| `/api/scheduler/config/` | GET · PUT · PATCH | Global scheduler settings |
| `/api/scheduler/notifications/` | GET · PATCH · DELETE | In-app notifications |
| `/api/scheduler/notifications/mark-all-read/` | PATCH | Bulk mark read |

#### `GET /api/scheduler/schedule/` — Query Parameters

| `view` | Required param | Returns |
|--------|---------------|---------|
| `section` | `student_group_id` (+ optional `timetable_id`) | Section weekly timetable |
| `faculty` | `faculty_id` | Faculty weekly schedule across all programs |
| `room` | `room_id` | Room occupancy across all programs |

---

## ⚙️ Installation

### Prerequisites
- Python 3.10+
- Node.js 18+
- pip

### 1. Backend Setup

```bash
cd server
python -m venv venv

# Windows
venv\Scripts\activate

# macOS / Linux
source venv/bin/activate

pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```

Backend runs at → `http://127.0.0.1:8000`

### 2. Frontend Setup

```bash
cd client
npm install
npm run dev
```

Frontend runs at → `http://localhost:5173`

### 3. Demo Login Credentials

| Role | Username | Password |
|------|----------|----------|
| Admin | `admin` | `admin123` |
| Teacher | `teacher` | `teacher123` |
| Student | `student` | `student123` |

### 4. ML Pipeline (Optional — pre-trained models included)

```bash
# Build graph from dataset
python manage.py build_graph

# Train GNN (generates node embeddings)
python ml_pipeline/gnn_model.py

# Train Random Forest predictor
python ml_pipeline/random_forest_model.py
```

---

## 📊 Development Status

### ✅ Completed

- [x] Backend — 4 Django apps, 15+ models, full CRUD REST APIs
- [x] Role-based frontend — 10 pages (Login, Dashboard, Programs, Sections, Faculty, Courses, Infrastructure, Generator, Timetables, Settings)
- [x] Demo authentication — Admin / Teacher / Student roles with route guards
- [x] Historical timetable dataset — 1300+ rows, 22 features
- [x] Heterogeneous graph — 5 node types, 7 edge types
- [x] GraphSAGE GNN — trained, 32-dim embeddings generated
- [x] Random Forest slot predictor v2 — 111-dim input, VotingClassifier ensemble
- [x] Constraint-based scheduler with ML integration and heuristic fallback
- [x] ML pipeline day-string bug fixed (`"MON"` → `"Monday"` mapping for inference)
- [x] Saturday / weekend scheduling support
- [x] Lab-first scheduling with consecutive slot enforcement
- [x] Bulk data upload (Excel) for Faculty and Courses
- [x] Timetable version management with auto-pruning
- [x] Auto-publish and notification triggers on generation
- [x] In-app notification bell with real-time polling
- [x] Role-based timetable views — Section / Faculty Schedule / Room Occupancy
- [x] Dynamic color-coded timetable grid with per-course legend
- [x] Global Scheduler Settings panel (hour caps, constraints, toggles)
- [x] Responsive UI — mobile sidebar overlay, 4-breakpoint CSS, light/dark theme

### 🔄 In Progress

- [ ] Advanced constraint reporting and conflict visualization
- [ ] Timetable analytics dashboard (workload distribution, room utilization)

### 🔮 Future Enhancements

- [ ] Reinforcement learning based optimization
- [ ] Genetic algorithm fallback scheduler
- [ ] Docker containerization
- [ ] PostgreSQL production database
- [ ] Real JWT-based authentication with user-section/faculty linkage
- [ ] Multi-institution / multi-campus support
- [ ] iCal / Google Calendar export

---

## 👨‍💻 Author

**Akhil**
BCA Student · Full-Stack Developer · AI Systems Enthusiast

---

## 📄 License

Developed for academic and educational purposes.
