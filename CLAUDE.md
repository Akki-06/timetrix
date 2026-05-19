# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Timetrix is a full-stack AI-assisted academic timetable generator. It uses a multi-phase greedy constraint-satisfaction engine backed by a GraphSAGE GNN + Random Forest ML pipeline to produce conflict-free timetables. The stack is Django 6 + PostgreSQL (backend) and React 19 + Vite 7 (frontend).

## Development Commands

### Backend (Django)
```bash
cd server
python manage.py runserver          # http://127.0.0.1:8000
python manage.py migrate
python manage.py makemigrations
python manage.py createsuperuser
```

### Frontend (React + Vite)
```bash
cd client
npm install
npm run dev      # http://localhost:5173
npm run build
npm run lint
```

### ML Pipeline Management Commands
```bash
cd server
python manage.py build_graph        # Build heterogeneous graph for GNN training
python manage.py update_ml_csvs     # Sync training CSVs from DB
python manage.py generate_figures   # Generate evaluation visualizations
python manage.py paper_metrics      # Compute scheduling quality metrics
python manage.py test_all_terms     # Run scheduling against all active terms
```

### Tests
```bash
cd server
python manage.py test                    # All tests
python manage.py test academics          # Per-app
python manage.py test scheduler.tests
```

### Environment
Requires a `.env` file at `server/` with:
```
DB_NAME, DB_USER, DB_PASSWORD, DB_HOST, DB_PORT, SECRET_KEY, DEBUG
```
PostgreSQL must be running on `localhost:5432`.

## Architecture

### Backend — `server/`

Four Django apps with a clear separation of concerns:

| App | Responsibility |
|-----|---------------|
| `academics` | Department → Program → AcademicTerm → StudentGroup + Course/CourseOffering hierarchy |
| `faculty` | Faculty profiles, availability windows, 3-level exclusions (program/semester/course) |
| `infrastructure` | Buildings, rooms (THEORY vs LAB), ProgramRoomMapping for affinities |
| `scheduler` | Timetable generation orchestration, LectureAllocation storage, SchedulerConfig singleton |
| `ml_pipeline` | Graph construction, GNN training, Random Forest scoring |

Settings and URL routing live in `server/config/`.

### Scheduler Engine — `server/scheduler/engine/`

The core scheduling logic in `runner.py` (~1900 lines) runs in four phases:

1. **LOAD** — Build in-memory state (courses, faculty, rooms, slots), compute difficulty scores, run feasibility checks.
2. **LABS** — Schedule lab offerings first (require 2 consecutive slots).
3. **THEORY** — Greedy pass ordered by difficulty: parallel electives (PE) → combined token offerings → standard courses. Followed by a repair pass for conflicts, then idle offerings.
4. **SAVE** — Bulk-insert `LectureAllocation` records, create `TimetableVersion`, fire `Notification`.

Supporting engine modules: `constraint_tracker.py` (no double-booking), `ml_scorer.py` (loads embeddings + RF model), `difficulty.py`, `feasibility.py`, `observability.py`.

### ML Pipeline — `server/ml_pipeline/`

Three-stage pipeline:

1. **Graph construction** (`graph_builder.py`) — Builds a heterogeneous NetworkX graph with 5 node types (Faculty, Course, Section, Room, TimeSlot) and 7 edge types from historical timetable data.
2. **GraphSAGE GNN** (`gnn_model.py`) — 2-layer GraphSAGE produces 32-dim embeddings per node. Trained via link-prediction (binary cross-entropy). Saved to `ml_pipeline/trained/gnn_model.pt` + `node_embeddings.pkl`.
3. **Random Forest** (`random_forest_model.py`) — VotingClassifier ensemble consuming 111-dim input (96 from GNN embeddings + 15 manual features). Outputs suitability score [0,1] per candidate Course-Slot-Room triple. Saved to `ml_pipeline/trained/random_forest_model.pt`.

Trained artifacts are gitignored. The scheduler falls back to heuristic scoring if models are unavailable.

### Key Models

**`CourseOffering`** (`academics/models.py`) is the central scheduling unit — it links Course → StudentGroup → Faculty and carries `weekly_load`, `elective_slot_group` (for parallel PE electives), and `combined_token` (for A+B section linking).

**`SchedulerConfig`** (`scheduler/models.py`) is a singleton (pk=1) storing all tunable parameters: role-based hour caps, hard constraint limits, and feature flags like `enforce_room_type` and `auto_publish`.

**`LectureAllocation`** (`scheduler/models.py`) is the output record: course_offering + room + timeslot + constraint scores.

### Frontend — `client/src/`

React 19 app with Context API (no Redux). Two contexts: `AuthContext` (demo auth — hardcoded roles, no JWT) and `ThemeContext`.

Routes are role-gated via `ProtectedRoute`. Admin-only pages cover the full data-entry pipeline (Programs → Sections → Faculty → Courses → Assignments → Eligibility → Infrastructure → Generator). The `GeneratedTimetablesPage` is accessible to all roles with view filtering by section/faculty/room.

**Demo credentials:** admin/admin123, teacher/teacher123, student/student123.

API base URL is `http://127.0.0.1:8000/api/` — configured in `client/src/utils/helpers.js` (or via Vite proxy).

### API Surface

- `/api/academics/` — CRUD for department, program, term, course, student-group, course-offering; bulk upload endpoints
- `/api/faculty/` — Faculty, availability, eligibility, exclusions, workload stats; bulk upload
- `/api/infrastructure/` — Building, room, program-room-map
- `/api/scheduler/` — `generate/` (POST triggers engine), `schedule/` (GET with `view=section|faculty|room`), `config/`, `notifications/`
