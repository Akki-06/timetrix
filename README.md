# ⏱️ TIMETRIX  
### 🧠 AI-Driven Constraint-Aware Academic Timetable Generation System

---

# 🚀 Overview

**TIMETRIX** is an intelligent academic timetable generation platform designed to automate university scheduling using **Artificial Intelligence, Graph Neural Networks, and Constraint-based Optimization**.

Timetable scheduling is a **complex NP-hard problem** involving multiple entities such as:

- 👩‍🏫 Faculty
- 📚 Courses
- 🧑‍🎓 Student Sections
- 🏫 Rooms & Laboratories
- ⏰ Time Slots

Manual scheduling often leads to conflicts, inefficient resource usage, and administrative overhead.

TIMETRIX addresses this by combining:

- 🧠 **Graph Neural Networks (GNN)**
- 🌲 **Random Forest Prediction**
- ⚙️ **Constraint-based Scheduling**

The system aims to automate **80–90% of timetable creation**.

---

# 🧠 Scheduling Architecture

TIMETRIX follows a **hybrid AI + constraint solving architecture**.

```
Historical Timetable Data
        ↓
Dataset Cleaning & Feature Engineering
        ↓
Graph Construction
        ↓
Graph Neural Network
        ↓
Node Embeddings
        ↓
Random Forest Slot Predictor
        ↓
Constraint Based Scheduler
        ↓
Final Timetable
```

---

# ✨ Core Features

### 📚 Academic Management
- Departments
- Programs
- Academic Terms
- Courses
- Student Groups
- Course Offerings

### 👩‍🏫 Faculty Management
- Faculty Profiles
- Subject Eligibility
- Availability Slots
- Workload Limits

### 🏫 Infrastructure Management
- Buildings
- Classrooms
- Laboratories
- Program-Room Mapping

### 🧠 Intelligent Scheduling
- Lab-first scheduling strategy
- Faculty workload balancing
- Conflict detection
- Constraint scoring
- Automated timetable generation

### 📂 Data Handling
- CSV dataset integration
- ML-ready data architecture
- Timetable export support

---

# 🤖 Machine Learning Architecture

## 🧠 Graph Neural Network (GNN)

Timetable data is modeled as a **graph structure**.

### Graph Nodes

- Faculty
- Course
- Section
- Room
- TimeSlot

### Graph Relationships

```
Faculty → teaches → Course
Course → belongs_to → Section
Course → scheduled_in → TimeSlot
Course → uses → Room
```

Frameworks used:

- PyTorch
- PyTorch Geometric
- NetworkX

The GNN learns structural relationships and generates **node embeddings**.

Example embedding:

```
DBMS → [0.41, -0.23, 0.78]
```

These embeddings capture hidden scheduling patterns.

---

## 🌲 Random Forest Slot Predictor

Random Forest predicts **slot suitability**.

Input features:

- teacher_embedding
- course_embedding
- section_embedding
- day_index
- slot_index
- room_type
- contact_hours_weekly

Output:

```
Probability(slot suitability)
```

Example:

```
Tue 10:35 → 0.86
Wed 11:30 → 0.72
Fri 9:40 → 0.21
```

Slots are ranked before final scheduling.

---

## ⚙️ Constraint Based Scheduler

Machine learning predictions are validated using strict scheduling rules.

### Hard Constraints

- Teacher cannot teach two classes simultaneously
- Room cannot host two classes simultaneously
- Lab sessions must occupy consecutive slots
- Faculty workload limits
- Lunch break protection

The scheduler selects the **highest ranked valid slot**.

---

# 📊 Dataset

TIMETRIX uses **historical timetable data from the university**.

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

![Python](https://img.shields.io/badge/Python-3776AB?logo=python&logoColor=white)
![Django](https://img.shields.io/badge/Django-092E20?logo=django&logoColor=white)
![Django REST](https://img.shields.io/badge/Django_REST_Framework-red)

## Frontend

![React](https://img.shields.io/badge/React-20232A?logo=react)
![Vite](https://img.shields.io/badge/Vite-646CFF?logo=vite)

## Data Processing

![Pandas](https://img.shields.io/badge/Pandas-150458?logo=pandas)
![NumPy](https://img.shields.io/badge/NumPy-013243?logo=numpy)

## Machine Learning

![Scikit Learn](https://img.shields.io/badge/scikit--learn-F7931E?logo=scikit-learn)

## Deep Learning

![PyTorch](https://img.shields.io/badge/PyTorch-EE4C2C?logo=pytorch)

## Graph Processing

![NetworkX](https://img.shields.io/badge/NetworkX-black)

---

# 📁 Project Structure

```
TIMETRIX
│
├── client/                     # React frontend (Vite)
│   ├── src/
│   │   ├── api/
│   │   ├── components/
│   │   ├── layouts/
│   │   ├── pages/
│   │   ├── routes/
│   │   └── utils/
│   │
│   ├── eslint.config.js
│   ├── vite.config.js
│   └── package.json
│
├── server/                     # Django backend
│   │
│   ├── manage.py
│   │
│   ├── config/                 # Django configuration
│   │   ├── settings.py
│   │   ├── urls.py
│   │   ├── asgi.py
│   │   └── wsgi.py
│   │
│   ├── academics/              # Academic structure models
│   ├── faculty/                # Faculty constraints
│   ├── infrastructure/         # Buildings & rooms
│   ├── scheduler/              # Scheduling engine
│   │
│   └── ml_pipeline/            # Machine learning pipeline
│       ├── graph_builder.py
│       ├── gnn_model.py
│       └── random_forest_model.py
│
├── requirements.txt
├── .gitignore
└── README.md
```

---

# ⚙️ Installation

## Backend Setup

```
cd server
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
python manage.py makemigrations
python manage.py migrate
python manage.py runserver
```

Backend runs at:

```
http://127.0.0.1:8000
```

---

## Frontend Setup

```
cd client
npm install
npm run dev
```

Frontend runs at:

```
http://localhost:5173
```

---

# 📊 Development Status

### Completed

- Backend architecture implemented
- Database models created
- CRUD APIs implemented
- Frontend dashboard prototype
- Historical timetable dataset collected
- Graph dataset prepared
- GNN prototype implemented
- Random Forest slot predictor implemented

### In Progress

- Constraint based scheduler
- Full ML pipeline integration
- Automated timetable generation

---

# 🔮 Future Enhancements

- Reinforcement learning scheduling
- Genetic algorithm optimization
- Docker deployment
- PostgreSQL production database
- Role based authentication
- Multi-institution support

---

# 👨‍💻 Author

**Akhil**  
BCA Student  
Full-Stack Developer & AI Systems Enthusiast

---

# 📄 License

Developed for academic and educational purposes.
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
