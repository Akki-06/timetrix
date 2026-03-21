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
- Course definitions (theory / lab, contact hours, priority)
- Student groups and sections
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
- Teaching capacity constraints per subject

### 🏫 Infrastructure Management
- Buildings, classrooms, laboratories
- Room capacity and type tracking
- Program-room mapping and allocation preferences

### 🤖 Intelligent Scheduling
- **Lab-first strategy** — schedule labs before theory (limited lab rooms)
- **Consecutive slot enforcement** — lab sessions span 2 contiguous slots
- **Faculty workload balancing** — role-based hour limits respected
- **Conflict detection** — faculty / room / group double-booking prevention
- **ML-based candidate ranking** — RF scores all (faculty, room, day, slot) combos
- **Graceful degradation** — heuristic fallback if ML models unavailable
- **Lunch break protection** — enforced across all sections

### 📂 Data Handling
- Historical CSV dataset integration (1300+ records)
- Bulk upload support via frontend
- Timetable export to Excel (`.xlsx`)
- Version management for generated timetables

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
```

**Frameworks:** PyTorch 2.10 · PyTorch Geometric 2.7 · NetworkX 3.6

The GNN is trained via **link prediction** (real edges vs. 7-type negative samples) and produces **32-dimensional node embeddings** that capture hidden scheduling patterns.

---

### 🌲 Random Forest Slot Predictor

The RF model ranks scheduling candidates by **slot suitability probability**.

#### Input Features — 111 Dimensions Total

```
faculty_embedding   (32-dim)  ─┐
course_embedding    (32-dim)   ├─ GNN embeddings (96-dim)
section_embedding   (32-dim)  ─┘
+
day_index           (manual)  ─┐
slot_index          (manual)   │
room_type           (manual)   │ Manual features (15-dim)
contact_hours_weekly(manual)   │
... (11 more)                 ─┘
```

#### Output — Suitability Score

```
Tue 10:35  →  0.86  ✅ High suitability
Wed 11:30  →  0.72  ✅ Good
Fri 09:40  →  0.21  ❌ Poor fit
```

Candidates are ranked by score before being validated against hard constraints.

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
│   │   │   ├── ActivitySection.jsx
│   │   │   ├── BulkUploadCard.jsx
│   │   │   ├── Sidebar.jsx
│   │   │   ├── StatsSection.jsx
│   │   │   ├── TermStatusSection.jsx
│   │   │   └── TopNavbar.jsx
│   │   ├── layouts/                 # Page layout wrappers
│   │   ├── pages/                   # Application pages
│   │   │   ├── Dashboard.jsx
│   │   │   ├── FacultyPage.jsx
│   │   │   ├── CoursesPage.jsx
│   │   │   ├── InfrastructurePage.jsx
│   │   │   ├── TimetableGeneratorPage.jsx
│   │   │   ├── GeneratedTimetablesPage.jsx
│   │   │   └── SettingsPage.jsx
│   │   ├── routes/AppRoutes.jsx
│   │   └── utils/
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
│   ├── academics/                   # Departments, Programs, Courses, Terms
│   ├── faculty/                     # Faculty profiles, availability, eligibility
│   ├── infrastructure/              # Buildings, rooms, program-room mapping
│   ├── scheduler/                   # Scheduling engine + API
│   │   ├── scheduler_engine.py      # Core ML-integrated scheduling logic
│   │   └── views.py                 # GenerateTimetableView
│   └── ml_pipeline/                 # Machine learning pipeline
│       ├── data/                    # Training datasets (CSV)
│       │   ├── timetable_dataset.csv    (1300+ rows, 22 features)
│       │   ├── faculty_metadata.csv
│       │   ├── rooms.csv
│       │   └── timeslots.csv
│       ├── trained/                 # Saved model artifacts
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

| Prefix | App | Description |
|--------|-----|-------------|
| `/api/academics/` | academics | Departments, Programs, Courses, Terms, Groups |
| `/api/faculty/` | faculty | Faculty profiles, availability, eligibility |
| `/api/infrastructure/` | infrastructure | Buildings, rooms, mappings |
| `/api/scheduler/` | scheduler | Timetable generation, allocation retrieval |

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

### 3. ML Pipeline (Optional — pre-trained models included)

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

- [x] Backend architecture — 4 Django apps, 15+ models
- [x] Full CRUD REST APIs with filtering, search, ordering
- [x] Frontend — 7 pages (Dashboard, Faculty, Courses, Infrastructure, Generator, Timetables, Settings)
- [x] Historical timetable dataset — 1300+ rows, 22 features
- [x] Heterogeneous graph construction with 5 node types
- [x] GraphSAGE GNN — trained, 32-dim embeddings generated
- [x] Random Forest slot predictor v2 — 111-dim input, suitability scoring
- [x] Constraint-based scheduler engine with ML integration
- [x] Lab-first scheduling strategy with consecutive slot enforcement
- [x] Bulk data upload and Excel export support

### 🔄 In Progress

- [ ] Full end-to-end ML pipeline integration and testing
- [ ] Timetable conflict visualization on frontend
- [ ] Advanced constraint reporting and analytics

### 🔮 Future Enhancements

- [ ] Reinforcement learning based optimization
- [ ] Genetic algorithm fallback scheduler
- [ ] Docker containerization
- [ ] PostgreSQL production database
- [ ] Role-based authentication (Admin / Faculty / Student)
- [ ] Multi-institution / multi-campus support

---

## 👨‍💻 Author

**Akhil**
BCA Student · Full-Stack Developer · AI Systems Enthusiast

---

## 📄 License

Developed for academic and educational purposes.
