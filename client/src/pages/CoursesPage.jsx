import { useCallback, useEffect, useState } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import BulkUploadCard from "../components/BulkUploadCard";
import { asList, extractError } from "../utils/helpers";
import { FaBook, FaTrash, FaEdit, FaTimes } from "react-icons/fa";

/* ────────────────────────────────────────────
   Course type definitions matching backend
   ──────────────────────────────────────────── */
const COURSE_TYPES = [
  // Schedulable: theory-style, credit-mapped
  { value: "PC",  label: "Program Core",              group: "theory" },
  { value: "PE",  label: "Program Elective",          group: "theory" },
  { value: "OE",  label: "Open Elective",             group: "theory" },
  { value: "BSC", label: "Basic Sciences Course",     group: "theory" },
  { value: "ESC", label: "Engineering Sciences Course",group: "theory" },
  { value: "HUM", label: "Humanities",                group: "theory" },
  // Schedulable: fixed 1 slot regardless of credits
  { value: "LS",  label: "Life Skills",               group: "fixed" },
  { value: "VAM", label: "Value Added Module",        group: "fixed" },
  { value: "AEC", label: "Ability Enhancement Course", group: "fixed" },
  // Schedulable: lab
  { value: "PR",  label: "Practical (Lab)",           group: "lab" },
  // Not schedulable
  { value: "PRJ", label: "Project",                   group: "project" },
  { value: "DIS", label: "Dissertation",              group: "none" },
  { value: "INT", label: "Internship",                group: "none" },
  { value: "RND", label: "Research",                  group: "none" },
];

const TYPE_MAP = {};
COURSE_TYPES.forEach((t) => { TYPE_MAP[t.value] = t; });

/* ────────────────────────────────────────────
   Credit → Weekly-lectures formula
   (derived from 743-course DBUU syllabus data)
   ──────────────────────────────────────────── */
function lecturesFromCredits(credits, courseType) {
  // PRJ and PR: always 1 session/week (scheduler handles 2 consecutive slots)
  if (courseType === "PR" || courseType === "PRJ") return 1;
  // Truly non-schedulable
  if (courseType === "DIS" || courseType === "INT" || courseType === "RND") return 0;
  // Everything else (PC, PE, OE, BSC, ESC, HUM, LS, VAM, AEC): credit-mapped
  return Math.min(Number(credits) || 0, 4);
}

function isLabType(ct) {
  return ct === "PR";
}

function isNonSchedulable(ct) {
  return ct === "DIS" || ct === "INT" || ct === "RND";
}

const INITIAL_FORM = {
  program: "",
  semester: "",
  code: "",
  name: "",
  credits: 3,
  course_type: "PC",
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

  // Filters
  const [filterProgram, setFilterProgram] = useState("");
  const [filterSem, setFilterSem] = useState("");
  const [filterType, setFilterType] = useState("");

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

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const weeklyLectures = lecturesFromCredits(form.credits, form.course_type);
  const lab = isLabType(form.course_type);
  const nonSched = isNonSchedulable(form.course_type);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSubmitting(true);

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
    setError("");
    setSuccess("");
  };

  const cancelEdit = () => {
    setEditId(null);
    setForm(INITIAL_FORM);
    setError("");
    setSuccess("");
  };

  const handleDelete = async (id) => {
    try {
      await api.delete(`academics/courses/${id}/`);
      loadAll();
    } catch (err) {
      setError(extractError(err, "Failed to delete course."));
    }
  };

  const filteredCourses = courses.filter((c) => {
    if (filterProgram && String(c.program) !== String(filterProgram)) return false;
    if (filterSem && String(c.semester) !== String(filterSem)) return false;
    if (filterType && c.course_type !== filterType) return false;
    return true;
  });

  return (
    <DashboardLayout>
      <div className="page-head">
        <h1>Course Management</h1>
        <p>Create and assign courses to programs and semesters.</p>
      </div>

      <BulkUploadCard
        title="Upload Courses Master Data"
        endpoint="academics/courses/bulk-upload/"
        useFileUpload
        requiredColumns={["code", "name", "credits", "course_type", "program_code", "semester"]}
        templateFileName="courses-upload-template.xlsx"
        templateSampleRow={{
          code: "BCA501",
          name: "Advanced Algorithms",
          credits: 3,
          course_type: "PC",
          program_code: "BCA",
          semester: 5,
        }}
        onUploadComplete={loadAll}
      />

      <BulkUploadCard
        title="Upload Program Elective Choices"
        endpoint="academics/courses/bulk-upload/"
        useFileUpload
        requiredColumns={["code", "name", "credits", "course_type", "program_code", "semester", "parent_pe_code"]}
        templateFileName="pe-choices-template.xlsx"
        templateSampleRow={{
          code: "24COA2A1",
          name: "Cyber Security",
          credits: 3,
          course_type: "PE",
          program_code: "BCA",
          semester: 4,
          parent_pe_code: "24COA2AX_BCA",
        }}
        onUploadComplete={loadAll}
      />

      <div className="faculty-two-col">
        {/* ── LEFT: Add Course Form ── */}
        <section className="data-card faculty-form-card">
          <h3>
            <FaBook style={{ marginRight: 8, color: "var(--brand)" }} />
            {editId ? "Update Course" : "Add New Course"}
          </h3>

          {error && <p className="upload-error">{error}</p>}
          {success && <p className="upload-success">{success}</p>}

          <form className="faculty-register-form" onSubmit={handleSubmit}>
            {/* Program */}
            <div className="form-group">
              <label className="form-label">Select Program</label>
              <select
                className="input"
                value={form.program}
                onChange={(e) =>
                  setForm((p) => ({ ...p, program: e.target.value }))
                }
              >
                <option value="">Choose program</option>
                {programs.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.display_name || p.name} ({p.code})
                  </option>
                ))}
              </select>
            </div>

            {/* Semester */}
            <div className="form-group">
              <label className="form-label">Semester</label>
              <select
                className="input"
                value={form.semester}
                onChange={(e) =>
                  setForm((p) => ({ ...p, semester: e.target.value }))
                }
              >
                <option value="">Choose semester</option>
                {Array.from(
                  { length: (() => {
                    const sel = programs.find((p) => String(p.id) === String(form.program));
                    return sel?.total_semesters || 8;
                  })() },
                  (_, i) => i + 1
                ).map((s) => (
                  <option key={s} value={s}>
                    Semester {s}
                  </option>
                ))}
              </select>
            </div>

            {/* Course Code */}
            <div className="form-group">
              <label className="form-label">Course Code *</label>
              <input
                className="input"
                placeholder="e.g. 24COA103"
                value={form.code}
                onChange={(e) =>
                  setForm((p) => ({ ...p, code: e.target.value }))
                }
                required
              />
            </div>

            {/* Course Name */}
            <div className="form-group">
              <label className="form-label">Course Name *</label>
              <input
                className="input"
                placeholder="e.g. Data Structures"
                value={form.name}
                onChange={(e) =>
                  setForm((p) => ({ ...p, name: e.target.value }))
                }
                required
              />
            </div>

            {/* Course Type */}
            <div className="form-group">
              <label className="form-label">Course Type *</label>
              <select
                className="input"
                value={form.course_type}
                onChange={(e) =>
                  setForm((p) => ({ ...p, course_type: e.target.value }))
                }
              >
                {COURSE_TYPES.map((ct) => (
                  <option key={ct.value} value={ct.value}>
                    {ct.value} – {ct.label}
                  </option>
                ))}
              </select>
            </div>

            {/* Credits */}
            <div className="form-group">
              <label className="form-label">Credits *</label>
              <input
                className="input"
                type="number"
                min="0"
                max="20"
                placeholder="e.g. 4"
                value={form.credits}
                onChange={(e) =>
                  setForm((p) => ({ ...p, credits: e.target.value }))
                }
                required
              />
              <span className="input-hint">
                {form.course_type === "PRJ" ? (
                  <>1 guided session / week (2 consecutive slots in lecture hall)</>
                ) : nonSched ? (
                  <>Not scheduled — self-directed / off-campus</>
                ) : (
                  <>
                    Weekly lectures: <strong>{weeklyLectures} hrs</strong>
                    {" "}(from credits)
                  </>
                )}
              </span>
            </div>

            {/* Lab indicator */}
            {lab && (
              <div className="form-group">
                <span className="input-hint" style={{ color: "var(--brand)" }}>
                  Lab courses require lab room &amp; consecutive slots (auto-set)
                </span>
              </div>
            )}

            <div className="form-group form-group-btn" style={{ display: "flex", gap: "10px" }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={submitting}
                style={{ flex: 1, justifyContent: "center" }}
              >
                <FaBook style={{ marginRight: 8 }} />
                {submitting ? "Saving..." : editId ? "Update Course" : "Create Course"}
              </button>
              {editId && (
                <button
                  type="button"
                  className="btn btn-secondary"
                  onClick={cancelEdit}
                >
                  <FaTimes />
                </button>
              )}
            </div>
          </form>
        </section>

        {/* ── RIGHT: Existing Courses ── */}
        <section className="data-card faculty-list-card">
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: "1rem", flexWrap: "wrap", gap: "10px" }}>
            <h3 style={{ margin: 0 }}>Existing Courses ({filteredCourses.length})</h3>
            <div style={{ display: "flex", gap: "10px", flexWrap: "wrap" }}>
              <select className="input" style={{ width: "150px" }} value={filterProgram} onChange={e => setFilterProgram(e.target.value)}>
                <option value="">All Programs</option>
                {programs.map(p => (
                  <option key={p.id} value={p.id}>{p.code}</option>
                ))}
              </select>
              <select className="input" style={{ width: "120px" }} value={filterSem} onChange={e => setFilterSem(e.target.value)}>
                <option value="">All Sems</option>
                {[1,2,3,4,5,6,7,8].map(s => (
                  <option key={s} value={s}>Sem {s}</option>
                ))}
              </select>
              <select className="input" style={{ width: "130px" }} value={filterType} onChange={e => setFilterType(e.target.value)}>
                <option value="">All Types</option>
                {COURSE_TYPES.map(ct => (
                  <option key={ct.value} value={ct.value}>{ct.value}</option>
                ))}
              </select>
            </div>
          </div>
          {loading ? (
            <p className="upload-help">Loading course data...</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Course Name</th>
                    <th>Type</th>
                    <th>Credits</th>
                    <th>Weekly</th>
                    <th>Program</th>
                    <th>Sem</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {filteredCourses.length === 0 ? (
                    <tr>
                      <td
                        colSpan="8"
                        style={{
                          textAlign: "center",
                          color: "var(--muted)",
                          padding: 24,
                        }}
                      >
                        No courses found matching criteria.
                      </td>
                    </tr>
                  ) : (
                    filteredCourses.map((c) => {
                      const typeInfo = TYPE_MAP[c.course_type];
                      const badgeClass = typeInfo
                        ? typeInfo.group
                        : "theory";
                      return (
                        <tr key={c.id}>
                          <td>
                            <strong>{c.code}</strong>
                          </td>
                          <td>
                            <div className="fac-name-cell">
                              <FaBook
                                style={{
                                  color: "var(--brand)",
                                  flexShrink: 0,
                                }}
                              />
                              <span>{c.name}</span>
                            </div>
                          </td>
                          <td>
                            <span
                              className={`course-type-badge ${badgeClass}`}
                            >
                              {c.course_type}
                            </span>
                          </td>
                          <td>{c.credits}</td>
                          <td>
                            {c.max_weekly_lectures > 0
                              ? `${c.max_weekly_lectures} hrs`
                              : "—"}
                          </td>
                          <td>
                            {c.program_name || (
                              <span style={{ color: "var(--muted)" }}>—</span>
                            )}
                          </td>
                          <td>
                            {c.semester ? (
                              <span className="course-sem-badge">
                                Sem {c.semester}
                              </span>
                            ) : (
                              <span style={{ color: "var(--muted)" }}>—</span>
                            )}
                          </td>
                          <td>
                            <div className="table-actions">
                              <button
                                className="action-btn"
                                onClick={() => handleEdit(c)}
                                title="Edit Course"
                              >
                                <FaEdit style={{ color: "#3b82f6" }} />
                              </button>
                              <button
                                className="action-btn danger"
                                onClick={() => handleDelete(c.id)}
                                title="Delete Course"
                              >
                                <FaTrash />
                              </button>
                            </div>
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
    </DashboardLayout>
  );
}

export default CoursesPage;
