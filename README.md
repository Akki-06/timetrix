# 📅 TIMETRIX  
### Constraint-Aware Automated Academic Timetable Generation System

---

## 🚀 Overview

**TIMETRIX** is a full-stack academic timetable management system designed to generate, manage, and optimize institutional timetables using structured constraints.

### ✨ Key Features
- 🏫 Academic Structure Management  
- 👩‍🏫 Faculty Constraint Handling  
- 🏢 Infrastructure & Room Allocation  
- 📊 Conflict-Free Timetable Generation  
- 📁 Excel/CSV Data Import & Export  
- ⚙️ Future AI/ML-Based Optimization  

Built with a modular and scalable architecture to support intelligent scheduling and future automation.

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