import { useCallback, useEffect, useState, useMemo } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import BulkUploadCard from "../components/BulkUploadCard";
import { asList, extractError, courseDisplayCode } from "../utils/helpers";
import {
  FaBook, FaTrash, FaEdit, FaTimes, FaPlus, FaFlask, FaSearch,
  FaGraduationCap, FaLayerGroup,
  FaChevronDown, FaChevronRight,
} from "react-icons/fa";

const COURSE_TYPES = [
  { value: "PC",  label: "Program Core",               group: "theory"  },
  { value: "PE",  label: "Program Elective",            group: "theory"  },
  { value: "OE",  label: "Open Elective",               group: "theory"  },
  { value: "BSC", label: "Basic Sciences Course",       group: "theory"  },
  { value: "ESC", label: "Engineering Sciences Course", group: "theory"  },
  { value: "HUM", label: "Humanities",                  group: "theory"  },
  { value: "LS",  label: "Life Skills",                 group: "fixed"   },
  { value: "VAM", label: "Value Added Module",          group: "fixed"   },
  { value: "AEC", label: "Ability Enhancement Course",  group: "fixed"   },
  { value: "PR",  label: "Practical (Lab)",             group: "lab"     },
  { value: "PRJ", label: "Project",                     group: "project" },
  { value: "DIS", label: "Dissertation",                group: "none"    },
  { value: "INT", label: "Internship",                  group: "none"    },
  { value: "RND", label: "Research",                    group: "none"    },
];
const TYPE_MAP = {};
COURSE_TYPES.forEach((t) => { TYPE_MAP[t.value] = t; });

function lecturesFromCredits(credits, courseType) {
  if (courseType === "PR" || courseType === "PRJ") return 1;
  if (courseType === "DIS" || courseType === "INT" || courseType === "RND") return 0;
  return Math.min(Number(credits) || 0, 4);
}

const INITIAL_FORM = {
  program: "", semester: "", code: "", name: "", credits: 3, course_type: "PC",
};

function CoursesPage() {
  const [courses, setCourses] = useState([]);
  const [programs, setPrograms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [form, setForm] = useState(INITIAL_FORM);
  const [editId, setEditId] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [search, setSearch] = useState("");

  /* Expandable state */
  const [expandedProgs, setExpandedProgs] = useState({});
  const [expandedSems, setExpandedSems] = useState({});

  const loadAll = useCallback(async () => {
    try {
      setLoading(true);
      const [courseResp, progResp] = await Promise.all([
        api.get("academics/courses/").catch(() => null),
        api.get("academics/programs/").catch(() => null),
      ]);
      setCourses(courseResp ? asList(courseResp.data) : []);
      setPrograms(progResp ? asList(progResp.data) : []);
    } catch (err) {
      console.error("Failed to load data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  const weeklyLectures = lecturesFromCredits(form.credits, form.course_type);
  const lab = form.course_type === "PR";
  const nonSched = ["DIS", "INT", "RND"].includes(form.course_type);

  const semesterOptions = useMemo(() => {
    const prog = programs.find((p) => String(p.id) === String(form.program));
    const max = prog?.total_semesters || 8;
    return Array.from({ length: max }, (_, i) => i + 1);
  }, [form.program, programs]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(""); setSuccess(""); setSubmitting(true);
    const courseType = form.course_type;
    const lectures = lecturesFromCredits(form.credits, courseType);
    try {
      const payload = {
        code: form.code,
        name: form.name,
        credits: Number(form.credits),
        course_type: courseType,
        min_weekly_lectures: lectures,
        max_weekly_lectures: lectures,
        priority: 1,
        requires_lab_room: lab,
        requires_consecutive_slots: lab || courseType === "PRJ",
      };
      if (form.program) payload.program = Number(form.program);
      if (form.semester) payload.semester = Number(form.semester);

      if (editId) {
        await api.patch(`academics/courses/${editId}/`, payload);
        setSuccess("Course updated successfully.");
        setEditId(null);
      } else {
        await api.post("academics/courses/", payload);
        setSuccess("Course created successfully.");
      }
      setForm(INITIAL_FORM);
      setShowForm(false);
      loadAll();
    } catch (err) {
      setError(extractError(err, editId ? "Failed to update course." : "Failed to create course."));
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (course) => {
    setEditId(course.id);
    setForm({
      program: course.program || "",
      semester: course.semester || "",
      code: course.code,
      name: course.name,
      credits: course.credits,
      course_type: course.course_type,
    });
    setShowForm(true);
    setError(""); setSuccess("");
  };

  const cancelEdit = () => {
    setEditId(null);
    setForm(INITIAL_FORM);
    setShowForm(false);
    setError(""); setSuccess("");
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this course?")) return;
    try {
      await api.delete(`academics/courses/${id}/`);
      loadAll();
    } catch (err) {
      setError(extractError(err, "Failed to delete course."));
    }
  };

  /* Build hierarchy: Program → Semester → Courses */
  const hierarchy = useMemo(() => {
    const q = search.toLowerCase();
    const filtered = q
      ? courses.filter(
          (c) =>
            (c.code || "").toLowerCase().includes(q) ||
            (c.name || "").toLowerCase().includes(q) ||
            (c.course_type || "").toLowerCase().includes(q)
        )
      : courses;

    const map = {};
    filtered.forEach((c) => {
      const progId = c.program || "none";
      if (!map[progId]) {
        const prog = programs.find((p) => p.id === c.program);
        map[progId] = {
          progId,
          progName: prog?.display_name || prog?.name || "Unassigned",
          progCode: prog?.code || "",
          totalCourses: 0,
          labCount: 0,
          semesters: {},
        };
      }
      map[progId].totalCourses++;
      if (c.course_type === "PR") map[progId].labCount++;
      const sem = c.semester || 0;
      if (!map[progId].semesters[sem]) map[progId].semesters[sem] = [];
      map[progId].semesters[sem].push(c);
    });

    return Object.values(map).sort((a, b) => a.progName.localeCompare(b.progName));
  }, [courses, programs, search]);

  const toggleProg = (id) => setExpandedProgs((p) => ({ ...p, [id]: !p[id] }));
  const toggleSem = (key) => setExpandedSems((p) => ({ ...p, [key]: !p[key] }));



  return (
    <DashboardLayout>
      {/* Header */}
      <div className="sec-page-header">
        <div>
          <h1 className="sec-page-title">Courses</h1>
          <p className="sec-page-sub">
            Create, import, and browse courses organised by program and semester.
          </p>
        </div>
        <button className="sec-add-btn" onClick={() => { setShowForm(!showForm); setEditId(null); setForm(INITIAL_FORM); }}>
          {showForm ? <><FaTimes /> Close</> : <><FaPlus /> Add Course</>}
        </button>
      </div>

      {error && <div className="sec-alert sec-alert-error">{error}</div>}
      {success && <div className="sec-alert sec-alert-success">{success}</div>}

      {/* Form Panel */}
      {showForm && (
        <div className="sec-form-panel">
          <div className="sec-form-header">
            <h3>{editId ? "Update Course" : "Add New Course"}</h3>
          </div>
          <form className="sec-form-grid" onSubmit={handleSubmit}>
            <div className="sec-field">
              <label>Program</label>
              <select
                value={form.program}
                onChange={(e) => setForm((p) => ({ ...p, program: e.target.value, semester: "" }))}
              >
                <option value="">Choose program</option>
                {[...programs].sort((a, b) => (a.display_name || a.name || "").localeCompare(b.display_name || b.name || "")).map((p) => (
                  <option key={p.id} value={p.id}>{p.display_name || p.name} ({p.code})</option>
                ))}
              </select>
            </div>

            <div className="sec-field">
              <label>Semester</label>
              <select
                value={form.semester}
                onChange={(e) => setForm((p) => ({ ...p, semester: e.target.value }))}
                disabled={!form.program}
              >
                <option value="">{form.program ? "Choose semester" : "Select program first"}</option>
                {semesterOptions.map((s) => (
                  <option key={s} value={s}>Semester {s}</option>
                ))}
              </select>
            </div>

            <div className="sec-field">
              <label>Course Code <span className="sec-req">*</span></label>
              <input
                placeholder="e.g. 24COA103"
                value={form.code}
                onChange={(e) => setForm((p) => ({ ...p, code: e.target.value }))}
                required
              />
            </div>

            <div className="sec-field">
              <label>Course Name <span className="sec-req">*</span></label>
              <input
                placeholder="e.g. Data Structures"
                value={form.name}
                onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                required
              />
            </div>

            <div className="sec-field">
              <label>Course Type <span className="sec-req">*</span></label>
              <select
                value={form.course_type}
                onChange={(e) => setForm((p) => ({ ...p, course_type: e.target.value }))}
              >
                {COURSE_TYPES.map((ct) => (
                  <option key={ct.value} value={ct.value}>{ct.value} – {ct.label}</option>
                ))}
              </select>
            </div>

            <div className="sec-field">
              <label>Credits <span className="sec-req">*</span></label>
              <input
                type="number" min="0" max="20"
                value={form.credits}
                onChange={(e) => setForm((p) => ({ ...p, credits: e.target.value }))}
                required
              />
              <span style={{ fontSize: 11, color: "var(--muted)" }}>
                {nonSched
                  ? "Not scheduled"
                  : form.course_type === "PRJ"
                  ? "1 guided session / week"
                  : `${weeklyLectures} hrs/wk`}
              </span>
            </div>

            {lab && (
              <div className="sec-field sec-field-wide">
                <span style={{ fontSize: 12, color: "var(--brand)", fontWeight: 600 }}>
                  Lab — requires lab room & consecutive slots (auto-set)
                </span>
              </div>
            )}

            <div className="sec-form-actions">
              <button type="submit" className="sec-submit-btn" disabled={submitting}>
                {submitting ? "Saving..." : editId ? "Update Course" : "Create Course"}
              </button>
              {editId && (
                <button type="button" className="sec-cancel-btn" onClick={cancelEdit}>Cancel</button>
              )}
            </div>
          </form>
        </div>
      )}

      {/* Bulk Upload */}
      <div className="data-card" style={{ marginBottom: 16 }}>
        <div className="courses-upload-row">
          <div className="courses-upload-col">
            <BulkUploadCard
              title="Upload Courses Master Data"
              endpoint="academics/courses/bulk-upload/"
              useFileUpload
              requiredColumns={["code", "name", "credits", "course_type", "program_code", "semester"]}
              templateFileName="courses-upload-template.xlsx"
              templateSampleRow={{
                code: "BCA501", name: "Advanced Algorithms",
                credits: 3, course_type: "PC", program_code: "BCA", semester: 5,
              }}
              onUploadComplete={loadAll}
            />
          </div>
          <div className="courses-upload-sep"><hr className="courses-hr" /></div>
          <div className="courses-upload-col">
            <BulkUploadCard
              title="Upload Program Elective Choices"
              endpoint="academics/courses/bulk-upload/"
              useFileUpload
              requiredColumns={["code", "name", "credits", "course_type", "program_code", "semester", "parent_pe_code"]}
              templateFileName="pe-choices-template.xlsx"
              templateSampleRow={{
                code: "24COA2A1", name: "Cyber Security",
                credits: 3, course_type: "PE",
                program_code: "BCA", semester: 4,
                parent_pe_code: "24COA2AX_BCA",
              }}
              onUploadComplete={loadAll}
            />
          </div>
        </div>
      </div>

      {/* Content */}
      {loading ? (
        <div className="sec-loading">
          <div className="sec-loading-spinner" />
          Loading courses...
        </div>
      ) : courses.length === 0 ? (
        <div className="sec-empty">
          <FaBook className="sec-empty-icon" />
          <h3>No courses registered yet</h3>
          <p>Click "Add Course" to register your first course.</p>
        </div>
      ) : (
        <div className="sec-hierarchy">
          {/* Summary */}
          <div className="sec-summary-strip">
            <div className="sec-summary-item">
              <FaGraduationCap />
              <span><strong>{hierarchy.length}</strong> Programs</span>
            </div>
            <div className="sec-summary-item">
              <FaBook />
              <span><strong>{courses.length}</strong> Courses</span>
            </div>
            <div className="sec-summary-item">
              <FaFlask />
              <span><strong>{courses.filter((c) => c.course_type === "PR").length}</strong> Labs</span>
            </div>
            <div style={{ marginLeft: "auto" }}>
              <div className="pdc-search-wrap">
                <FaSearch className="pdc-search-icon" />
                <input
                  className="input pdc-search-input"
                  placeholder="Search courses..."
                  value={search}
                  onChange={(e) => setSearch(e.target.value)}
                />
              </div>
            </div>
          </div>

          {/* Program → Semester → Course cards */}
          {hierarchy.map((prog) => (
            <div key={prog.progId} className="sec-program-block">
              <button className="sec-program-header" onClick={() => toggleProg(prog.progId)}>
                <div className="sec-program-left">
                  {expandedProgs[prog.progId] ? <FaChevronDown size={12} /> : <FaChevronRight size={12} />}
                  <div className="sec-program-icon"><FaGraduationCap /></div>
                  <div>
                    <span className="sec-program-name">{prog.progName}</span>
                  </div>
                </div>
                <div className="sec-program-meta">
                  <span className="sec-meta-badge">{prog.totalCourses} courses</span>
                  {prog.labCount > 0 && <span className="sec-meta-badge">{prog.labCount} labs</span>}
                </div>
              </button>

              {expandedProgs[prog.progId] && (
                <div className="sec-years-container">
                  {Object.entries(prog.semesters)
                    .sort(([a], [b]) => Number(a) - Number(b))
                    .map(([sem, semCourses]) => {
                      const semKey = `${prog.progId}-${sem}`;
                      return (
                        <div key={semKey} className="sec-year-block">
                          <button className="sec-year-header" onClick={() => toggleSem(semKey)}>
                            {expandedSems[semKey] ? <FaChevronDown size={10} /> : <FaChevronRight size={10} />}
                            <span className="sec-year-label">
                              {Number(sem) ? `Semester ${sem}` : "Unassigned"}
                            </span>
                            <span className="sec-year-count">{semCourses.length} courses</span>
                          </button>

                          {expandedSems[semKey] && (
                            <div className="sec-cards-grid">
                              {semCourses.map((c) => {
                                const info = TYPE_MAP[c.course_type];
                                const dispCode = courseDisplayCode(c.display_code || c.code);
                                return (
                                  <div key={c.id} className="sec-card">
                                    <div className="sec-card-top">
                                      <div className="sec-card-name-row">
                                        <span className="sec-card-name" style={{ fontSize: 15 }}>{dispCode}</span>
                                        <span className="sec-card-sem-badge">{c.course_type}</span>
                                      </div>
                                      <div className="sec-card-actions">
                                        <button className="sec-icon-btn" title="Edit" onClick={() => handleEdit(c)}>
                                          <FaEdit />
                                        </button>
                                        <button className="sec-icon-btn sec-icon-danger" title="Delete" onClick={() => handleDelete(c.id)}>
                                          <FaTrash />
                                        </button>
                                      </div>
                                    </div>

                                    <div className="sec-card-details">
                                      <div className="sec-detail-row">
                                        <span className="sec-detail-label">Name</span>
                                        <span className="sec-detail-value">{c.name}</span>
                                      </div>
                                      <div className="sec-detail-row">
                                        <span className="sec-detail-label">Credits</span>
                                        <span className="sec-detail-value">{c.credits}</span>
                                      </div>
                                      {c.max_weekly_lectures > 0 && (
                                        <div className="sec-detail-row">
                                          <span className="sec-detail-label">Weekly</span>
                                          <span className="sec-detail-value">{c.max_weekly_lectures} hrs/wk</span>
                                        </div>
                                      )}
                                      <div className="sec-detail-row">
                                        <span className="sec-detail-label">Type</span>
                                        <span className="sec-detail-value">{info?.label || c.course_type}</span>
                                      </div>
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          )}
                        </div>
                      );
                    })}
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </DashboardLayout>
  );
}

export default CoursesPage;
