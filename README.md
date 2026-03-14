# 📅 TIMETRIX
### AI-Driven Constraint-Aware Academic Timetable Generation System

---

# 🚀 Overview

**TIMETRIX** is an intelligent academic timetable generation system designed to automate university scheduling using **machine learning, graph neural networks (GNN), and constraint-based optimization**.

Timetable scheduling in universities is a complex **constraint satisfaction problem (CSP)** involving teachers, courses, classrooms, labs, and student groups. Manual scheduling often leads to conflicts, inefficient resource use, and large administrative overhead.

TIMETRIX solves this by learning patterns from **historical timetable datasets** and combining them with **constraint-aware scheduling algorithms**.

The system aims to automate **80-90% of timetable generation**, leaving only minimal manual adjustments.

---

# 🧠 Core Scheduling Strategy

TIMETRIX uses a **hybrid architecture combining AI and rule-based constraint solving**.

Pipeline:

```
Historical Timetable Data
        ↓
Dataset Cleaning & Encoding
        ↓
Graph Construction
        ↓
Graph Neural Network (GNN)
        ↓
Node Embeddings
        ↓
Feature Engineering
        ↓
Random Forest Slot Predictor
        ↓
Constraint-Based Scheduler
        ↓
Final Timetable
```

---

# ✨ Key Features

### Academic Management
- Departments
- Programs
- Academic Terms
- Courses
- Student Groups
- Course Offerings

### Faculty Management
- Faculty profiles
- Subject eligibility
- Availability slots
- Workload limits

### Infrastructure Management
- Buildings
- Classrooms
- Laboratories
- Program-room mapping

### Intelligent Scheduling
- Lab-first scheduling strategy
- Conflict detection
- Faculty workload balancing
- Constraint-aware timetable generation

### Data Handling
- CSV dataset import
- ML-ready data structure
- Timetable export support

---

# 🧠 AI / Machine Learning Architecture

## Graph Representation

The timetable environment is modeled as a **heterogeneous graph**.

### Nodes

```
Faculty
Course
StudentGroup / Section
Room
TimeSlot
```

### Relationships

```
Faculty → teaches → Course
Course → belongs_to → Section
Course → scheduled_in → TimeSlot
Course → uses → Room
```

Graph libraries used:

```
NetworkX
PyTorch Geometric
```

---

## Graph Neural Network (GNN)

The GNN learns structural relationships between scheduling entities.

Frameworks used:

```
PyTorch
PyTorch Geometric
NetworkX
```

GNN generates **node embeddings** representing entities such as:

```
teacher_embedding
course_embedding
section_embedding
room_embedding
```

Example embedding vector:

```
DBMS → [0.41, -0.23, 0.78]
```

These embeddings encode scheduling patterns learned from historical data.

---

## Random Forest Slot Predictor

Random Forest predicts the **suitability of a time slot** for scheduling a course.

Library:

```
scikit-learn
```

Input features:

```
teacher_embedding
course_embedding
section_embedding
day_index
slot_index
room_is_lab
contact_hours_weekly
```

Output:

```
Probability(slot is suitable)
```

Example:

```
Tue 10:35 → 0.86
Wed 11:30 → 0.73
Fri 9:40 → 0.22
```

Slots are ranked and passed to the scheduler.

---

## Constraint-Based Scheduler

Machine learning predictions are validated using strict scheduling rules.

Hard constraints enforced:

```
Teacher cannot teach two classes simultaneously
Room cannot host two classes simultaneously
Lab sessions must occupy consecutive slots
Teacher workload limits must be respected
Lunch break slot must remain free
```

The scheduler selects the **highest scoring valid slot**.

---

# 📊 Dataset

TIMETRIX uses **historical timetable data collected from the university**.

Example dataset fields:

```
academic_year
semester_type
program
semester
section
course_code
course_name
faculty
room
day
day_index
slot_index
session_type
is_lab
group
is_elective_split
is_consecutive_lab
contact_hours_weekly
```

Dataset characteristics:

```
1300+ rows
22 features
```

Each row represents a **historical scheduling decision**.

---

# 🧱 Tech Stack

## Backend

```
Python
Django
Django REST Framework
SQLite (development)
```

## Frontend

```
React
Vite
Axios
React Router
```

## Data Processing

```
pandas
numpy
```

## Machine Learning

```
scikit-learn
Random Forest
```

## Deep Learning

```
PyTorch
PyTorch Geometric
```

## Graph Processing

```
NetworkX
```

---

# 📁 Project Structure

```
TIMETRIX
│
├── client/                     # React frontend
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── layouts/
│   │   ├── pages/
│   │   ├── routes/
│   │   └── utils/
│
├── server/                     # Django backend
│   ├── academics/
│   ├── faculty/
│   ├── infrastructure/
│   ├── scheduler/
│   └── config/
│
├── ml_models/                  # Machine learning models
│   ├── dataset_builder.py
│   ├── graph_builder.py
│   ├── gnn_model.py
│   └── random_forest_model.py
│
├── data/                       # Historical timetable datasets
│
├── requirements.txt
└── README.md
```

---

# ⚙️ Installation

## Backend

```
cd server
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```

Backend:

```
http://127.0.0.1:8000/
```

---

## Frontend

```
cd client
npm install
npm run dev
```

Frontend:

```
http://localhost:5173/
```

---

# 📊 Development Status

Completed

```
Backend architecture created
Database models implemented
CRUD APIs built
Frontend dashboard prototype
Historical timetable dataset collected
Graph dataset prepared
GNN prototype implemented
Random Forest slot predictor implemented
```

In Progress

```
Constraint-based scheduling engine
Full ML pipeline integration
Automated timetable generation
```

---

# 🔮 Future Enhancements

```
Reinforcement learning scheduling
Genetic algorithm optimization
Docker deployment
PostgreSQL production database
Role-based authentication
Multi-institution support
```

---

# 👨‍💻 Author

**Akhil**

BCA Student  
Full-Stack Developer & AI Systems Enthusiast

---

# 📄 License

This project is developed for academic and educational purposes.
---

## 🧱 Tech Stack

### 🔹 Backend
- 🐍 Python  
- 🌐 Django  
- 🔗 Django REST Framework  
- 🗄 SQLite (Development)  
- 🧩 django-filter  

### 🔹 Frontend
- ⚛️ React (Vite)  
- 🌍 Axios  
- 🧭 React Router  

---

## 📁 Project Structure

```bash
TIMETRIX/
│
├── client/                # React Frontend
│   ├── src/
│   │   ├── api/           # Axios configuration
│   │   ├── components/    # Reusable UI components
│   │   ├── layouts/       # Layout structures
│   │   ├── pages/         # Application pages
│   │   ├── routes/        # Routing configuration
│   │   ├── styles/        # Global styles
│   │   └── utils/         # Utility functions
│
├── server/                # Django Backend
│   ├── academics/         # Academic structure models
│   ├── faculty/           # Faculty constraints & availability
│   ├── infrastructure/    # Buildings & rooms
│   ├── scheduler/         # Timetable engine
│   └── config/            # Django configuration
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

## ⚙️ Core Modules

### 🏫 Academic Management
- Departments  
- Programs  
- Academic Terms  
- Courses  
- Student Groups  
- Course Offerings  

### 👩‍🏫 Faculty Management
- Faculty Profiles  
- Availability Scheduling  
- Subject Eligibility  
- Workload Constraints  

### 🏢 Infrastructure
- Buildings  
- Rooms  
- Program-Room Mapping  

### 🗓 Scheduler
- TimeSlot Configuration  
- Manual Timetable Builder  
- Conflict Detection  
- Versioned Timetables  
- Constraint Scoring  
- Finalization Protection  

### 📂 Data Management
- Upload Excel/CSV  
- Download Format Templates  
- Export Timetable (PDF/Excel/CSV)  

---

## 🧠 System Capabilities

- ✔ Hard Constraint Enforcement  
- ✔ Soft Constraint Scoring  
- ✔ Conflict Prevention (Room / Faculty / Student Group)  
- ✔ Faculty Workload Balancing  
- ✔ Versioned Timetable Management  
- ✔ Manual + Future Auto Generation  
- ✔ ML-Ready Data Architecture  

---

## 🛠 Installation Guide

### 🔹 Backend Setup

```bash
cd server
python -m venv venv
venv\Scripts\activate   # Windows
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```

Backend runs at:

```
http://127.0.0.1:8000/
```

---

### 🔹 Frontend Setup

```bash
cd client
npm install
npm run dev
```

Frontend runs at:

```
http://localhost:5173/
```

---

## 📊 Future Enhancements

- 🤖 AI-Based Timetable Optimization  
- 🧬 Genetic Algorithm Scheduling  
- 📈 Predictive Constraint Adjustment  
- 📦 Docker Deployment  
- 🗄 PostgreSQL Integration  
- 🌐 Role-Based Authentication  

---

## 👨‍💻 Author

**Akhil**  
BCA Student | Aspiring Full-Stack Developer  
Focused on building scalable academic systems and future-ready AI-integrated applications.

---

## 📄 License

This project is developed for academic and educational purposes.  
All rights reserved.
