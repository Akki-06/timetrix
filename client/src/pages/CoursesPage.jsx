import { useCallback, useEffect, useState } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import BulkUploadCard from "../components/BulkUploadCard";
import { toBoolean, toNumber } from "../utils/spreadsheet";
import { asList, extractError } from "../utils/helpers";
import { FaBook, FaTrash } from "react-icons/fa";

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
  { value: "PRJ", label: "Project",                   group: "none" },
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
  const c = Number(credits) || 0;
  const info = TYPE_MAP[courseType];
  if (!info) return c;

  switch (info.group) {
    case "theory": return c;                    // 1 credit = 1 lecture
    case "lab":    return c * 2;                // 1 credit = 2 practical hrs
    case "fixed":  return c >= 4 ? 1 : Math.max(c, 1); // mentoring: capped
    case "none":   return 0;                    // not schedulable
    default:       return c;
  }
}

function isLabType(ct) {
  return ct === "PR";
}

function isNonSchedulable(ct) {
  const info = TYPE_MAP[ct];
  return info?.group === "none";
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

    const lectures = lecturesFromCredits(form.credits, form.course_type);

    try {
      const payload = {
        code: form.code,
        name: form.name,
        credits: Number(form.credits),
        course_type: form.course_type,
        min_weekly_lectures: lectures,
        max_weekly_lectures: lectures,
        priority: 1,
        requires_lab_room: lab,
        requires_consecutive_slots: lab,
      };
      if (form.program) payload.program = Number(form.program);
      if (form.semester) payload.semester = Number(form.semester);

      await api.post("academics/courses/", payload);

      setForm(INITIAL_FORM);
      setSuccess("Course created successfully.");
      loadAll();
    } catch (err) {
      setError(extractError(err, "Failed to create course."));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await api.delete(`academics/courses/${id}/`);
      loadAll();
    } catch (err) {
      setError(extractError(err, "Failed to delete course."));
    }
  };

  return (
    <DashboardLayout>
      <div className="page-head">
        <h1>Course Management</h1>
        <p>Create and assign courses to programs and semesters.</p>
      </div>

      <BulkUploadCard
        title="Upload Courses"
        endpoint="academics/courses/"
        requiredColumns={["code", "name", "credits"]}
        templateFileName="courses-upload-template.xlsx"
        templateSampleRow={{
          code: "BCA501",
          name: "Advanced Algorithms",
          credits: 3,
          course_type: "PC",
          min_weekly_lectures: 3,
          max_weekly_lectures: 3,
          priority: 1,
          requires_lab_room: false,
          requires_consecutive_slots: false,
        }}
        mapRow={(row) => {
          const credits = toNumber(row.credits, 3);
          const ct = String(row.course_type || "PC").toUpperCase();
          const lectures = lecturesFromCredits(credits, ct);
          return {
            code: row.code,
            name: row.name,
            credits,
            course_type: ct,
            min_weekly_lectures: toNumber(row.min_weekly_lectures, lectures),
            max_weekly_lectures: toNumber(row.max_weekly_lectures, lectures),
            priority: toNumber(row.priority, 1),
            requires_lab_room: ct === "PR" || toBoolean(row.requires_lab_room, false),
            requires_consecutive_slots: toBoolean(
              row.requires_consecutive_slots,
              ct === "PR"
            ),
          };
        }}
        onUploadComplete={loadAll}
      />

      <div className="faculty-two-col">
        {/* ── LEFT: Add Course Form ── */}
        <section className="data-card faculty-form-card">
          <h3>
            <FaBook style={{ marginRight: 8, color: "var(--brand)" }} />
            Add New Course
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
                    {p.name} ({p.code})
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
                {[1, 2, 3, 4, 5, 6, 7, 8].map((s) => (
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
                {nonSched ? (
                  <>Not schedulable (self-directed / off-campus)</>
                ) : (
                  <>
                    Weekly lectures: <strong>{weeklyLectures} hrs</strong>
                    {" "}(auto-derived from credits &amp; type)
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

            <div className="form-group form-group-btn">
              <button
                type="submit"
                className="btn-primary btn-with-icon"
                disabled={submitting}
                style={{ width: "100%", justifyContent: "center" }}
              >
                <FaBook />
                {submitting ? "Creating..." : "Create Course"}
              </button>
            </div>
          </form>
        </section>

        {/* ── RIGHT: Existing Courses ── */}
        <section className="data-card faculty-list-card">
          <h3>Existing Courses ({courses.length})</h3>
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
                  {courses.length === 0 ? (
                    <tr>
                      <td
                        colSpan="8"
                        style={{
                          textAlign: "center",
                          color: "var(--muted)",
                          padding: 24,
                        }}
                      >
                        No courses yet. Add one using the form.
                      </td>
                    </tr>
                  ) : (
                    courses.map((c) => {
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
                            <button
                              className="icon-btn danger"
                              title="Delete"
                              onClick={() => handleDelete(c.id)}
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
    </DashboardLayout>
  );
}

export default CoursesPage;
