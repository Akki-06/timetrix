import { useCallback, useEffect, useState, useMemo } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import BulkUploadCard from "../components/BulkUploadCard";
import { asList, extractError, courseDisplayCode } from "../utils/helpers";
import {
  FaBook, FaTrash, FaEdit, FaTimes,
  FaChevronRight, FaChevronLeft, FaFlask,
  FaGraduationCap, FaLayerGroup,
} from "react-icons/fa";

/* ─────────────────────────── Course type definitions ─────────────────────────── */
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

/* ══════════════════════════════════════════════════════════════════════════
   Semester badge component — re-uses .course-sem-badge CSS
   ══════════════════════════════════════════════════════════════════════════ */
function SemBadge({ sem }) {
  return (
    <span className="course-sem-badge" style={{ fontSize: 11, padding: "2px 7px" }}>
      S{sem}
    </span>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
   Program Card — shown in the Program List panel
   ══════════════════════════════════════════════════════════════════════════ */
function ProgramCard({ prog, courses, onClick }) {
  const progCourses = courses.filter((c) => String(c.program) === String(prog.id));
  const sems = [...new Set(progCourses.map((c) => c.semester).filter(Boolean))].sort(
    (a, b) => a - b
  );
  const labCount = progCourses.filter((c) => c.course_type === "PR").length;

  return (
    <button
      className="prog-card"
      onClick={() => onClick(prog)}
      title={`View courses for ${prog.display_name || prog.name}`}
    >
      {/* Left icon */}
      <div className="prog-card-icon">
        <FaGraduationCap />
      </div>

      {/* Middle: name + meta */}
      <div className="prog-card-body">
        <div className="prog-card-name">
          {prog.display_name || prog.name}
        </div>
        <div className="prog-card-meta">
          <span className="prog-card-count">
            <FaLayerGroup style={{ fontSize: 10, marginRight: 3 }} />
            {progCourses.length} courses
          </span>
          {labCount > 0 && (
            <span className="prog-card-labs">
              <FaFlask style={{ fontSize: 10, marginRight: 3 }} />
              {labCount} labs
            </span>
          )}
          <span className="prog-card-sems">
            {sems.map((s) => (
              <SemBadge key={s} sem={s} />
            ))}
          </span>
        </div>
      </div>

      {/* Right: chevron */}
      <div className="prog-card-arrow">
        <FaChevronRight />
      </div>
    </button>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
   Program Detail Panel — courses grouped by semester
   ══════════════════════════════════════════════════════════════════════════ */
function ProgramDetail({ prog, courses, onBack, onEdit, onDelete }) {
  const [filterType, setFilterType] = useState("");

  const progCourses = useMemo(
    () => courses.filter((c) => String(c.program) === String(prog.id)),
    [courses, prog.id]
  );

  const filtered = useMemo(
    () => (filterType ? progCourses.filter((c) => c.course_type === filterType) : progCourses),
    [progCourses, filterType]
  );

  // Group by semester
  const bySem = useMemo(() => {
    const map = {};
    filtered.forEach((c) => {
      const k = c.semester ?? 0;
      if (!map[k]) map[k] = [];
      map[k].push(c);
    });
    return Object.entries(map)
      .sort(([a], [b]) => Number(a) - Number(b))
      .map(([sem, list]) => ({ sem: Number(sem), list }));
  }, [filtered]);

  const typesPresent = [...new Set(progCourses.map((c) => c.course_type))].sort();

  return (
    <div className="prog-detail">
      {/* Header */}
      <div className="prog-detail-header">
        <button className="prog-back-btn" onClick={onBack}>
          <FaChevronLeft /> Back
        </button>
        <div className="prog-detail-title">
          <FaGraduationCap style={{ color: "var(--brand)", marginRight: 8 }} />
          {prog.display_name || prog.name}
        </div>
        <div className="prog-detail-count">{progCourses.length} courses</div>
      </div>

      {/* Type filter chips */}
      <div className="prog-detail-filters">
        <button
          className={`type-chip ${filterType === "" ? "active" : ""}`}
          onClick={() => setFilterType("")}
        >
          All
        </button>
        {typesPresent.map((t) => {
          const info = TYPE_MAP[t];
          return (
            <button
              key={t}
              className={`type-chip type-chip-${info?.group || "theory"} ${filterType === t ? "active" : ""}`}
              onClick={() => setFilterType(t === filterType ? "" : t)}
            >
              {t}
            </button>
          );
        })}
      </div>

      {/* Semester sections */}
      <div className="prog-detail-body">
        {bySem.length === 0 ? (
          <p style={{ color: "var(--muted)", fontSize: 13, textAlign: "center", padding: 24 }}>
            No courses match the filter.
          </p>
        ) : (
          bySem.map(({ sem, list }) => (
            <div key={sem} className="sem-section">
              <div className="sem-section-header">
                <SemBadge sem={sem || "?"} />
                <span className="sem-section-label">
                  {sem ? `Semester ${sem}` : "Unassigned"}
                </span>
                <span className="sem-section-count">{list.length} courses</span>
              </div>
              <div className="sem-course-grid">
                {list.map((c) => {
                  const info = TYPE_MAP[c.course_type];
                  const dispCode = c.display_code || courseDisplayCode(c.code);
                  return (
                    <div key={c.id} className="sem-course-card">
                      <div className="sem-course-top">
                        <code className="sem-course-code">{dispCode}</code>
                        <span className={`course-type-badge ${info?.group || "theory"}`}>
                          {c.course_type}
                        </span>
                      </div>
                      <div className="sem-course-name">{c.name}</div>
                      <div className="sem-course-meta">
                        <span>{c.credits} cr</span>
                        {c.max_weekly_lectures > 0 && (
                          <span>{c.max_weekly_lectures} hrs/wk</span>
                        )}
                      </div>
                      <div className="sem-course-actions">
                        <button
                          className="action-btn"
                          onClick={() => onEdit(c)}
                          title="Edit"
                        >
                          <FaEdit style={{ color: "#3b82f6" }} />
                        </button>
                        <button
                          className="action-btn danger"
                          onClick={() => onDelete(c.id)}
                          title="Delete"
                        >
                          <FaTrash />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            </div>
          ))
        )}
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
   Main Component
   ══════════════════════════════════════════════════════════════════════════ */
function CoursesPage() {
  const [courses, setCourses]     = useState([]);
  const [programs, setPrograms]   = useState([]);
  const [loading, setLoading]     = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]         = useState("");
  const [success, setSuccess]     = useState("");
  const [form, setForm]           = useState(INITIAL_FORM);
  const [editId, setEditId]       = useState(null);

  // Currently selected program for drill-down
  const [selectedProg, setSelectedProg] = useState(null);
  // Search / filter for program list
  const [progSearch, setProgSearch] = useState("");

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

  // Computed values from form
  const weeklyLectures = lecturesFromCredits(form.credits, form.course_type);
  const lab            = form.course_type === "PR";
  const nonSched       = ["DIS", "INT", "RND"].includes(form.course_type);

  /* ── Submit (create / update) ─────────────────────────── */
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(""); setSuccess(""); setSubmitting(true);
    const courseType = form.course_type;
    const lectures   = lecturesFromCredits(form.credits, courseType);
    try {
      const payload = {
        code:                       form.code,
        name:                       form.name,
        credits:                    Number(form.credits),
        course_type:                courseType,
        min_weekly_lectures:        lectures,
        max_weekly_lectures:        lectures,
        priority:                   1,
        requires_lab_room:          lab,
        requires_consecutive_slots: lab || courseType === "PRJ",
      };
      if (form.program) payload.program  = Number(form.program);
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
      program:     course.program  || "",
      semester:    course.semester || "",
      code:        course.code,
      name:        course.name,
      credits:     course.credits,
      course_type: course.course_type,
    });
    setError(""); setSuccess("");
    // scroll form into view
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const cancelEdit = () => {
    setEditId(null);
    setForm(INITIAL_FORM);
    setError(""); setSuccess("");
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this course?")) return;
    try {
      await api.delete(`academics/courses/${id}/`);
      // If the deleted course's program had this as last course, deselect
      loadAll();
    } catch (err) {
      setError(extractError(err, "Failed to delete course."));
    }
  };

  // Filtered program list for the right panel
  const filteredPrograms = useMemo(() => {
    const q = progSearch.toLowerCase();
    return programs
      .filter(
        (p) =>
          !q ||
          (p.display_name || p.name || "").toLowerCase().includes(q) ||
          (p.code || "").toLowerCase().includes(q)
      )
      .sort((a, b) =>
        (a.display_name || a.name || "").localeCompare(b.display_name || b.name || "")
      );
  }, [programs, progSearch]);

  return (
    <DashboardLayout>
      {/* ── Page Head ── */}
      <div className="page-head">
        <h1>Course Management</h1>
        <p>Create, import, and browse courses organised by program.</p>
      </div>

      {/* ══ Upload Section — side-by-side with hr separator ══ */}
      <div className="data-card" style={{ marginBottom: 16 }}>
        <div className="courses-upload-row">
          {/* Left: Master data upload */}
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

          {/* Middle separator */}
          <div className="courses-upload-sep">
            <hr className="courses-hr" />
          </div>

          {/* Right: PE choices upload */}
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

      {/* ══ Two-column: Form left | Programs right ══ */}
      <div className="faculty-two-col">

        {/* ── LEFT: Add / Edit Course Form ── */}
        <section className="data-card faculty-form-card">
          <h3>
            <FaBook style={{ marginRight: 8, color: "var(--brand)" }} />
            {editId ? "Update Course" : "Add New Course"}
          </h3>

          {error   && <p className="upload-error">{error}</p>}
          {success && <p className="upload-success">{success}</p>}

          <form className="faculty-register-form" onSubmit={handleSubmit}>
            {/* Program */}
            <div className="form-group">
              <label className="form-label">Select Program</label>
              <select
                className="input"
                value={form.program}
                onChange={(e) => setForm((p) => ({ ...p, program: e.target.value }))}
              >
                <option value="">— Choose program —</option>
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
                onChange={(e) => setForm((p) => ({ ...p, semester: e.target.value }))}
              >
                <option value="">— Choose semester —</option>
                {Array.from(
                  { length: (() => {
                    const sel = programs.find((p) => String(p.id) === String(form.program));
                    return sel?.total_semesters || 8;
                  })() },
                  (_, i) => i + 1
                ).map((s) => (
                  <option key={s} value={s}>Semester {s}</option>
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
                onChange={(e) => setForm((p) => ({ ...p, code: e.target.value }))}
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
                onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                required
              />
            </div>

            {/* Course Type */}
            <div className="form-group">
              <label className="form-label">Course Type *</label>
              <select
                className="input"
                value={form.course_type}
                onChange={(e) => setForm((p) => ({ ...p, course_type: e.target.value }))}
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
                min="0" max="20"
                value={form.credits}
                onChange={(e) => setForm((p) => ({ ...p, credits: e.target.value }))}
                required
              />
              <span className="input-hint">
                {nonSched
                  ? "Not scheduled — self-directed / off-campus"
                  : form.course_type === "PRJ"
                  ? "1 guided session / week"
                  : <>Weekly lectures: <strong>{weeklyLectures} hrs</strong></>}
              </span>
            </div>

            {lab && (
              <div className="form-group">
                <span className="input-hint" style={{ color: "var(--brand)" }}>
                  Lab — requires lab room &amp; consecutive slots (auto-set)
                </span>
              </div>
            )}

            <div className="form-group form-group-btn" style={{ display: "flex", gap: 10 }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={submitting}
                style={{ flex: 1, justifyContent: "center" }}
              >
                <FaBook style={{ marginRight: 8 }} />
                {submitting ? "Saving…" : editId ? "Update Course" : "Create Course"}
              </button>
              {editId && (
                <button type="button" className="btn btn-secondary" onClick={cancelEdit}>
                  <FaTimes />
                </button>
              )}
            </div>
          </form>
        </section>

        {/* ── RIGHT: Program list OR program detail ── */}
        <section className="data-card faculty-list-card" style={{ padding: 0, overflow: "hidden" }}>
          {selectedProg ? (
            /* ─── Program Detail ─── */
            <ProgramDetail
              prog={selectedProg}
              courses={courses}
              onBack={() => setSelectedProg(null)}
              onEdit={handleEdit}
              onDelete={handleDelete}
            />
          ) : (
            /* ─── Program List ─── */
            <div className="prog-list-panel">
              <div className="prog-list-header">
                <div>
                  <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "var(--text)" }}>
                    Programs
                  </h3>
                  <p style={{ margin: "2px 0 0", fontSize: 12, color: "var(--muted)" }}>
                    {programs.length} programs · {courses.length} total courses
                  </p>
                </div>
                <input
                  className="input"
                  placeholder="Search programs…"
                  value={progSearch}
                  onChange={(e) => setProgSearch(e.target.value)}
                  style={{ width: 180, padding: "7px 12px", fontSize: 13 }}
                />
              </div>

              {loading ? (
                <p className="upload-help" style={{ padding: "20px 20px" }}>
                  Loading programs…
                </p>
              ) : filteredPrograms.length === 0 ? (
                <p className="upload-help" style={{ padding: "20px 20px" }}>
                  No programs match your search.
                </p>
              ) : (
                <div className="prog-card-list">
                  {filteredPrograms.map((p) => (
                    <ProgramCard
                      key={p.id}
                      prog={p}
                      courses={courses}
                      onClick={setSelectedProg}
                    />
                  ))}
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </DashboardLayout>
  );
}

export default CoursesPage;
