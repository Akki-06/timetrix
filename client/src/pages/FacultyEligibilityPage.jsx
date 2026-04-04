import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import BulkUploadCard from "../components/BulkUploadCard";
import { asList, extractError } from "../utils/helpers";
import {
  FaLink,
  FaTrash,
  FaUserTie,
  FaChalkboardTeacher,
  FaSearch,
  FaFilter,
  FaTimes,
} from "react-icons/fa";

function workloadColor(remaining, max) {
  if (max === 0) return "wl-gray";
  const ratio = remaining / max;
  if (ratio <= 0.15) return "wl-red";
  if (ratio <= 0.4) return "wl-yellow";
  return "wl-green";
}

function workloadLabel(remaining) {
  if (remaining <= 0) return "Full";
  return `${remaining} hrs left`;
}

function FacultyEligibilityPage() {
  const [faculty, setFaculty] = useState([]);
  const [courses, setCourses] = useState([]);
  const [programs, setPrograms] = useState([]);
  const [eligibilities, setEligibilities] = useState([]);
  const [workloads, setWorkloads] = useState([]);
  const [loading, setLoading] = useState(true);

  // Form
  const [selFaculty, setSelFaculty] = useState("");
  const [selCourse, setSelCourse] = useState("");
  const [priority, setPriority] = useState(1);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  // Course picker filters
  const [courseSearch, setCourseSearch] = useState("");
  const [courseProgFilter, setCourseProgFilter] = useState("");
  const [courseSemFilter, setCourseSemFilter] = useState("");
  const [coursePickerOpen, setCoursePickerOpen] = useState(false);
  const coursePickerRef = useRef(null);

  // Eligibility table filters
  const [searchFac, setSearchFac] = useState("");
  const [searchCourse, setSearchCourse] = useState("");

  const loadAll = useCallback(async () => {
    try {
      setLoading(true);
      const [facR, courseR, progR, eligR, wlR] = await Promise.all([
        api.get("faculty/faculty/?is_active=true").catch(() => null),
        api.get("academics/courses/").catch(() => null),
        api.get("academics/programs/").catch(() => null),
        api.get("faculty/faculty-subject-eligibility/").catch(() => null),
        api.get("faculty/faculty/workload/").catch(() => null),
      ]);
      setFaculty(facR ? asList(facR.data) : []);
      setCourses(courseR ? asList(courseR.data) : []);
      setPrograms(progR ? asList(progR.data) : []);
      setEligibilities(eligR ? asList(eligR.data) : []);
      setWorkloads(wlR ? asList(wlR.data) : []);
    } catch (err) {
      console.error("Load error:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  // Close course picker on outside click
  useEffect(() => {
    const handler = (e) => {
      if (coursePickerRef.current && !coursePickerRef.current.contains(e.target)) {
        setCoursePickerOpen(false);
      }
    };
    document.addEventListener("mousedown", handler);
    return () => document.removeEventListener("mousedown", handler);
  }, []);

  // Workload map
  const wlMap = useMemo(() => {
    const m = {};
    workloads.forEach((w) => { m[w.id] = w; });
    return m;
  }, [workloads]);

  // Program map for display
  const progMap = useMemo(() => {
    const m = {};
    programs.forEach((p) => { m[p.id] = p; });
    return m;
  }, [programs]);

  // Unique semesters from courses
  const availSemesters = useMemo(() => {
    const s = new Set();
    courses.forEach((c) => {
      if (c.semester) s.add(c.semester);
    });
    return [...s].sort((a, b) => a - b);
  }, [courses]);

  // Filtered courses for the picker
  const filteredCourses = useMemo(() => {
    return courses.filter((c) => {
      if (courseProgFilter && String(c.program) !== courseProgFilter) return false;
      if (courseSemFilter && String(c.semester) !== courseSemFilter) return false;
      if (courseSearch) {
        const q = courseSearch.toLowerCase();
        const match =
          (c.code || "").toLowerCase().includes(q) ||
          (c.name || "").toLowerCase().includes(q) ||
          (c.program_name || "").toLowerCase().includes(q);
        if (!match) return false;
      }
      return true;
    });
  }, [courses, courseSearch, courseProgFilter, courseSemFilter]);

  // Group filtered courses by program → semester
  const groupedCourses = useMemo(() => {
    const groups = {};
    filteredCourses.forEach((c) => {
      const progName = c.program_name || "Unassigned";
      const sem = c.semester || 0;
      const key = `${progName}___${sem}`;
      if (!groups[key]) {
        groups[key] = { progName, sem, courses: [] };
      }
      groups[key].courses.push(c);
    });
    // Sort by program name then semester
    return Object.values(groups).sort((a, b) => {
      const cmp = a.progName.localeCompare(b.progName);
      if (cmp !== 0) return cmp;
      return a.sem - b.sem;
    });
  }, [filteredCourses]);

  // Selected course object
  const selectedCourseObj = useMemo(() => {
    if (!selCourse) return null;
    return courses.find((c) => String(c.id) === String(selCourse)) || null;
  }, [selCourse, courses]);

  // Filtered eligibility list
  const filtered = useMemo(() => {
    return eligibilities.filter((e) => {
      const facMatch =
        !searchFac ||
        (e.faculty_name || "").toLowerCase().includes(searchFac.toLowerCase());
      const courseMatch =
        !searchCourse ||
        (e.course_code || "").toLowerCase().includes(searchCourse.toLowerCase()) ||
        (e.course_name || "").toLowerCase().includes(searchCourse.toLowerCase());
      return facMatch && courseMatch;
    });
  }, [eligibilities, searchFac, searchCourse]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    if (!selFaculty || !selCourse) {
      setError("Select both faculty and course.");
      return;
    }
    setSubmitting(true);
    try {
      await api.post("faculty/faculty-subject-eligibility/", {
        faculty: Number(selFaculty),
        course: Number(selCourse),
        priority_weight: Number(priority),
      });
      setSuccess("Eligibility added successfully.");
      setSelFaculty("");
      setSelCourse("");
      setPriority(1);
      setCourseSearch("");
      loadAll();
    } catch (err) {
      setError(extractError(err, "Failed to add eligibility."));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Remove this eligibility record?")) return;
    try {
      await api.delete(`faculty/faculty-subject-eligibility/${id}/`);
      loadAll();
    } catch (err) {
      setError(extractError(err, "Failed to delete."));
    }
  };

  const sortedFaculty = useMemo(() => {
    return [...faculty].sort((a, b) => a.name.localeCompare(b.name));
  }, [faculty]);

  return (
    <DashboardLayout>
      <div className="page-head">
        <h1>Faculty–Course Eligibility</h1>
        <p>
          Map which faculty members can teach which courses. Upload from Excel
          or assign manually.
        </p>
      </div>

      {/* ── UPLOAD ── */}
      <BulkUploadCard
        title="Upload Eligibility Data"
        endpoint="faculty/eligibility/bulk-upload/"
        useFileUpload
        requiredColumns={["faculty_name", "course_code"]}
        templateFileName="eligibility-upload-template.xlsx"
        helperText="Excel must have columns: faculty_name, course_code. Optionally: priority_weight."
        templateSampleRow={{
          faculty_name: "Dr. Ritika Mehra",
          course_code: "24AML202",
          priority_weight: 1,
        }}
        onUploadComplete={loadAll}
      />

      <div className="faculty-two-col">
        {/* ── LEFT: Manual assign form ── */}
        <section className="data-card faculty-form-card">
          <h3>
            <FaLink style={{ marginRight: 8, color: "var(--brand)" }} />
            Assign Faculty to Course
          </h3>

          {error && <p className="upload-error">{error}</p>}
          {success && <p className="upload-success">{success}</p>}

          <form className="faculty-register-form" onSubmit={handleSubmit}>
            {/* Faculty select */}
            <div className="form-group">
              <label className="form-label">Faculty *</label>
              <select
                className="input"
                value={selFaculty}
                onChange={(e) => setSelFaculty(e.target.value)}
                required
              >
                <option value="">Choose faculty</option>
                {sortedFaculty.map((f) => {
                  const wl = wlMap[f.id];
                  const rem = wl ? wl.remaining : f.max_weekly_load;
                  const max = wl ? wl.max_weekly_load : f.max_weekly_load;
                  const color = workloadColor(rem, max);
                  const tag =
                    color === "wl-red"
                      ? "🔴"
                      : color === "wl-yellow"
                      ? "🟡"
                      : "🟢";
                  return (
                    <option key={f.id} value={f.id}>
                      {tag} {f.name} — {workloadLabel(rem)} (max {max})
                    </option>
                  );
                })}
              </select>
            </div>

            {/* Workload badge */}
            {selFaculty && (() => {
              const wl = wlMap[Number(selFaculty)];
              if (!wl) return null;
              const color = workloadColor(wl.remaining, wl.max_weekly_load);
              return (
                <div className={`wl-badge-card ${color}`}>
                  <FaUserTie style={{ marginRight: 6 }} />
                  <strong>{wl.name}</strong>
                  <span className="wl-stats">
                    {wl.current_load}/{wl.max_weekly_load} hrs used
                    &nbsp;·&nbsp;
                    <strong>{wl.remaining} remaining</strong>
                    &nbsp;·&nbsp;
                    {wl.eligible_courses} courses assigned
                  </span>
                </div>
              );
            })()}

            {/* ── Course Picker with Search + Program/Sem filters ── */}
            <div className="form-group" ref={coursePickerRef}>
              <label className="form-label">Course *</label>

              {/* Selected course display or search input */}
              {selectedCourseObj && !coursePickerOpen ? (
                <div className="course-selected-chip" onClick={() => setCoursePickerOpen(true)}>
                  <div className="course-chip-main">
                    <strong>{selectedCourseObj.code}</strong>
                    <span>{selectedCourseObj.name}</span>
                  </div>
                  <div className="course-chip-meta">
                    {selectedCourseObj.program_name && (
                      <span className="course-sem-badge">
                        {selectedCourseObj.program_name}
                      </span>
                    )}
                    {selectedCourseObj.semester && (
                      <span className="course-sem-badge">
                        Sem {selectedCourseObj.semester}
                      </span>
                    )}
                    <span className="course-sem-badge">
                      {selectedCourseObj.course_type}
                    </span>
                  </div>
                  <button
                    type="button"
                    className="course-chip-clear"
                    onClick={(e) => {
                      e.stopPropagation();
                      setSelCourse("");
                      setCourseSearch("");
                    }}
                  >
                    <FaTimes />
                  </button>
                </div>
              ) : (
                <div className="course-picker-input-wrap">
                  <FaSearch className="course-picker-search-icon" />
                  <input
                    className="input"
                    style={{ paddingLeft: 34 }}
                    placeholder="Search by course code or name..."
                    value={courseSearch}
                    onChange={(e) => {
                      setCourseSearch(e.target.value);
                      setCoursePickerOpen(true);
                    }}
                    onFocus={() => setCoursePickerOpen(true)}
                  />
                </div>
              )}

              {/* Dropdown with filters + grouped list */}
              {coursePickerOpen && (
                <div className="course-picker-dropdown">
                  {/* Filter bar */}
                  <div className="course-picker-filters">
                    <FaFilter style={{ color: "var(--muted)", fontSize: 12, flexShrink: 0 }} />
                    <select
                      className="input course-picker-filter-select"
                      value={courseProgFilter}
                      onChange={(e) => setCourseProgFilter(e.target.value)}
                    >
                      <option value="">All Programs</option>
                      {programs.map((p) => (
                        <option key={p.id} value={p.id}>
                          {p.code} — {p.display_name || p.name}
                        </option>
                      ))}
                    </select>
                    <select
                      className="input course-picker-filter-select"
                      value={courseSemFilter}
                      onChange={(e) => setCourseSemFilter(e.target.value)}
                    >
                      <option value="">All Sems</option>
                      {availSemesters.map((s) => (
                        <option key={s} value={s}>
                          Sem {s}
                        </option>
                      ))}
                    </select>
                    {(courseProgFilter || courseSemFilter) && (
                      <button
                        type="button"
                        className="course-picker-clear-btn"
                        onClick={() => {
                          setCourseProgFilter("");
                          setCourseSemFilter("");
                        }}
                        title="Clear filters"
                      >
                        <FaTimes />
                      </button>
                    )}
                  </div>

                  {/* Course list grouped by program → semester */}
                  <div className="course-picker-list">
                    {groupedCourses.length === 0 ? (
                      <div className="course-picker-empty">
                        No courses match your search.
                      </div>
                    ) : (
                      groupedCourses.map((group) => (
                        <div key={`${group.progName}___${group.sem}`} className="course-picker-group">
                          <div className="course-picker-group-header">
                            <span className="course-picker-prog-name">{group.progName}</span>
                            <span className="course-picker-sem-tag">Sem {group.sem || "?"}</span>
                            <span className="course-picker-count">({group.courses.length})</span>
                          </div>
                          {group.courses.map((c) => (
                            <button
                              type="button"
                              key={c.id}
                              className={`course-picker-item ${String(c.id) === String(selCourse) ? "selected" : ""}`}
                              onClick={() => {
                                setSelCourse(String(c.id));
                                setCoursePickerOpen(false);
                                setCourseSearch("");
                              }}
                            >
                              <span className="cpi-code">{c.code}</span>
                              <span className="cpi-name">{c.name}</span>
                              <span className="cpi-meta">
                                {c.credits}cr · {c.course_type}
                              </span>
                            </button>
                          ))}
                        </div>
                      ))
                    )}
                  </div>
                </div>
              )}
            </div>

            {/* Priority weight */}
            <div className="form-group">
              <label className="form-label">Priority Weight</label>
              <input
                className="input"
                type="number"
                min="1"
                max="10"
                value={priority}
                onChange={(e) => setPriority(e.target.value)}
              />
              <span className="input-hint">
                Higher = preferred for this course during scheduling.
              </span>
            </div>

            <div className="form-group form-group-btn">
              <button
                type="submit"
                className="btn-primary btn-with-icon"
                disabled={submitting}
                style={{ width: "100%", justifyContent: "center" }}
              >
                <FaLink />
                {submitting ? "Assigning..." : "Assign Eligibility"}
              </button>
            </div>
          </form>
        </section>

        {/* ── RIGHT: Eligibility records ── */}
        <section className="data-card faculty-list-card">
          <h3>
            <FaChalkboardTeacher
              style={{ marginRight: 8, color: "var(--brand)" }}
            />
            Existing Eligibilities ({eligibilities.length})
          </h3>

          {/* Search filters */}
          <div className="elig-search-row">
            <div className="elig-search-input">
              <FaSearch className="elig-search-icon" />
              <input
                className="input"
                placeholder="Filter by faculty..."
                value={searchFac}
                onChange={(e) => setSearchFac(e.target.value)}
              />
            </div>
            <div className="elig-search-input">
              <FaSearch className="elig-search-icon" />
              <input
                className="input"
                placeholder="Filter by course..."
                value={searchCourse}
                onChange={(e) => setSearchCourse(e.target.value)}
              />
            </div>
          </div>

          {loading ? (
            <p className="upload-help">Loading...</p>
          ) : (
            <div className="table-wrap" style={{ maxHeight: 500, overflow: "auto" }}>
              <table>
                <thead>
                  <tr>
                    <th>Faculty</th>
                    <th>Course</th>
                    <th>Workload</th>
                    <th>Wt</th>
                    <th></th>
                  </tr>
                </thead>
                <tbody>
                  {filtered.length === 0 ? (
                    <tr>
                      <td
                        colSpan="5"
                        style={{
                          textAlign: "center",
                          color: "var(--muted)",
                          padding: 24,
                        }}
                      >
                        No eligibility records. Upload or add manually.
                      </td>
                    </tr>
                  ) : (
                    filtered.map((e) => {
                      const wl = wlMap[e.faculty];
                      const rem = wl ? wl.remaining : "?";
                      const max = wl ? wl.max_weekly_load : "?";
                      const color = wl
                        ? workloadColor(wl.remaining, wl.max_weekly_load)
                        : "wl-gray";
                      return (
                        <tr key={e.id}>
                          <td>
                            <strong>{e.faculty_name}</strong>
                          </td>
                          <td>
                            <div>
                              <strong>{e.course_code}</strong>
                            </div>
                            <div
                              style={{
                                fontSize: "0.8rem",
                                color: "var(--muted)",
                              }}
                            >
                              {e.course_name}
                            </div>
                          </td>
                          <td>
                            <span className={`wl-pill ${color}`}>
                              {rem}/{max}
                            </span>
                          </td>
                          <td>{e.priority_weight}</td>
                          <td>
                            <button
                              className="icon-btn danger"
                              title="Remove"
                              onClick={() => handleDelete(e.id)}
                            >
                              <FaTrash />
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>

      {/* ── WORKLOAD OVERVIEW ── */}
      <section className="data-card" style={{ marginTop: 16 }}>
        <h3>Faculty Workload Overview</h3>
        {loading ? (
          <p className="upload-help">Loading...</p>
        ) : (
          <div className="wl-grid">
            {workloads.map((w) => {
              const color = workloadColor(w.remaining, w.max_weekly_load);
              const pct =
                w.max_weekly_load > 0
                  ? Math.round(
                      ((w.max_weekly_load - w.remaining) / w.max_weekly_load) *
                        100
                    )
                  : 0;
              return (
                <div key={w.id} className={`wl-card ${color}`}>
                  <div className="wl-card-name">{w.name}</div>
                  <div className="wl-card-role">{w.role}</div>
                  <div className="wl-bar-wrap">
                    <div
                      className="wl-bar-fill"
                      style={{ width: `${Math.min(pct, 100)}%` }}
                    />
                  </div>
                  <div className="wl-card-nums">
                    {w.current_load}/{w.max_weekly_load} hrs
                    <span className={`wl-pill ${color}`}>
                      {w.remaining} left
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </section>
    </DashboardLayout>
  );
}

export default FacultyEligibilityPage;
