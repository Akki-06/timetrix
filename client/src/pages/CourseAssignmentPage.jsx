import { useCallback, useEffect, useMemo, useState } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import BulkUploadCard from "../components/BulkUploadCard";
import { asList, extractError } from "../utils/helpers";
import {
  FaUserTie,
  FaSearch,
  FaCheck,
  FaFlask,
  FaBook,
  FaStar,
  FaLightbulb,
} from "react-icons/fa";

const TYPE_META = {
  PC:  { label: "Program Core",       icon: FaBook,      color: "#6366f1" },
  PE:  { label: "Program Elective",   icon: FaStar,      color: "#f59e0b" },
  OE:  { label: "Open Elective",      icon: FaLightbulb, color: "#14b8a6" },
  PR:  { label: "Practical (Lab)",    icon: FaFlask,     color: "#ef4444" },
  BSC: { label: "Basic Sciences",     icon: FaBook,      color: "#3b82f6" },
  ESC: { label: "Engineering Sci.",   icon: FaBook,      color: "#8b5cf6" },
  HUM: { label: "Humanities",         icon: FaBook,      color: "#ec4899" },
  LS:  { label: "Life Skills",        icon: FaLightbulb, color: "#10b981" },
  VAM: { label: "Value Added",        icon: FaLightbulb, color: "#06b6d4" },
  AEC: { label: "Ability Enhancement",icon: FaLightbulb, color: "#84cc16" },
  PRJ: { label: "Project",           icon: FaFlask,     color: "#f97316" },
};

function wlColor(remaining, max) {
  if (max === 0) return "wl-gray";
  const r = remaining / max;
  if (r <= 0.15) return "wl-red";
  if (r <= 0.4) return "wl-yellow";
  return "wl-green";
}

function wlEmoji(remaining, max) {
  const c = wlColor(remaining, max);
  if (c === "wl-red") return "🔴";
  if (c === "wl-yellow") return "🟡";
  return "🟢";
}

function CourseAssignmentPage() {
  const [programs, setPrograms] = useState([]);
  const [faculty, setFaculty] = useState([]);
  const [workloads, setWorkloads] = useState([]);
  const [studentGroups, setStudentGroups] = useState([]);
  const [offerings, setOfferings] = useState([]);
  const [loading, setLoading] = useState(false);

  // Selectors
  const [selProgram, setSelProgram] = useState("");
  const [selSemester, setSelSemester] = useState("");
  const [selSection, setSelSection] = useState("");

  // Assignment state
  const [saving, setSaving] = useState({});
  const [saved, setSaved] = useState({});
  const [searchQ, setSearchQ] = useState("");

  // ── Load initial data ──
  useEffect(() => {
    (async () => {
      const [progR, facR, wlR] = await Promise.all([
        api.get("academics/programs/").catch(() => null),
        api.get("faculty/faculty/?is_active=true").catch(() => null),
        api.get("faculty/faculty/workload/").catch(() => null),
      ]);
      setPrograms(progR ? asList(progR.data) : []);
      setFaculty(facR ? asList(facR.data) : []);
      setWorkloads(wlR ? asList(wlR.data) : []);
    })();
  }, []);

  // Workload map
  const wlMap = useMemo(() => {
    const m = {};
    workloads.forEach((w) => { m[w.id] = w; });
    return m;
  }, [workloads]);

  // Sorted active faculty
  const sortedFaculty = useMemo(() =>
    [...faculty].sort((a, b) => a.name.localeCompare(b.name)),
  [faculty]);

  // Available semesters for selected program
  const availSemesters = useMemo(() => {
    if (!selProgram) return [];
    const p = programs.find((pr) => String(pr.id) === selProgram);
    if (!p) return [];
    return Array.from({ length: p.total_semesters }, (_, i) => i + 1);
  }, [selProgram, programs]);

  // ── Load student groups when program+semester changes ──
  useEffect(() => {
    if (!selProgram || !selSemester) {
      setStudentGroups([]);
      setSelSection("");
      return;
    }
    (async () => {
      const r = await api
        .get(`academics/student-groups/?term__program=${selProgram}&term__semester=${selSemester}`)
        .catch(() => null);
      const groups = r ? asList(r.data) : [];
      setStudentGroups(groups);
      setSelSection(groups.length === 1 ? String(groups[0].id) : "");
    })();
  }, [selProgram, selSemester]);

  // ── Load offerings when section changes ──
  const loadOfferings = useCallback(async () => {
    if (!selSection) { setOfferings([]); return; }
    setLoading(true);
    const r = await api
      .get(`academics/course-offerings/?student_group=${selSection}`)
      .catch(() => null);
    setOfferings(r ? asList(r.data) : []);
    setLoading(false);
  }, [selSection]);

  useEffect(() => { loadOfferings(); }, [loadOfferings]);

  // ── Refresh workloads ──
  const refreshWorkloads = useCallback(async () => {
    const r = await api.get("faculty/faculty/workload/").catch(() => null);
    if (r) setWorkloads(asList(r.data));
  }, []);

  // ── Assign faculty ──
  const handleAssign = async (offeringId, facultyId) => {
    setSaving((p) => ({ ...p, [offeringId]: true }));
    try {
      await api.patch(`academics/course-offerings/${offeringId}/`, {
        assigned_faculty: facultyId || null,
      });
      setSaved((p) => ({ ...p, [offeringId]: true }));
      setTimeout(() => setSaved((p) => ({ ...p, [offeringId]: false })), 1500);
      // Update local state
      setOfferings((prev) =>
        prev.map((o) =>
          o.id === offeringId
            ? {
                ...o,
                assigned_faculty: facultyId || null,
                faculty_name: facultyId
                  ? (faculty.find((f) => f.id === Number(facultyId))?.name || null)
                  : null,
              }
            : o
        )
      );
      refreshWorkloads();
    } catch (err) {
      alert(extractError(err, "Failed to assign faculty."));
    } finally {
      setSaving((p) => ({ ...p, [offeringId]: false }));
    }
  };

  // ── Group offerings by course_type, and PE by elective_slot_group ──
  const grouped = useMemo(() => {
    const typeOrder = ["PC", "BSC", "ESC", "HUM", "PE", "OE", "PR", "PRJ", "LS", "VAM", "AEC"];
    const groups = {};

    const filtered = offerings.filter((o) => {
      if (!searchQ) return true;
      const q = searchQ.toLowerCase();
      return (
        (o.course_code || "").toLowerCase().includes(q) ||
        (o.course_name || "").toLowerCase().includes(q) ||
        (o.faculty_name || "").toLowerCase().includes(q)
      );
    });

    filtered.forEach((o) => {
      const t = o.course_type || "PC";
      if (!groups[t]) groups[t] = { type: t, items: [], electiveGroups: {} };

      if ((t === "PE" || t === "OE") && o.elective_slot_group) {
        const esg = o.elective_slot_group;
        if (!groups[t].electiveGroups[esg]) {
          groups[t].electiveGroups[esg] = [];
        }
        groups[t].electiveGroups[esg].push(o);
      } else {
        groups[t].items.push(o);
      }
    });

    return typeOrder
      .filter((t) => groups[t])
      .map((t) => groups[t]);
  }, [offerings, searchQ]);

  // ── Faculty dropdown renderer ──
  const FacultySelect = ({ offering }) => {
    const isSaving = saving[offering.id];
    const isSaved = saved[offering.id];
    return (
      <div className="ca-faculty-cell">
        <select
          className={`input ca-faculty-select ${isSaved ? "ca-saved" : ""}`}
          value={offering.assigned_faculty || ""}
          onChange={(e) => handleAssign(offering.id, e.target.value)}
          disabled={isSaving}
        >
          <option value="">— Unassigned —</option>
          {sortedFaculty.map((f) => {
            const wl = wlMap[f.id];
            const rem = wl ? wl.remaining : f.max_weekly_load;
            const max = wl ? wl.max_weekly_load : f.max_weekly_load;
            return (
              <option key={f.id} value={f.id}>
                {wlEmoji(rem, max)} {f.name} ({rem}/{max} hrs left)
              </option>
            );
          })}
        </select>
        {isSaving && <span className="ca-saving-indicator">Saving...</span>}
        {isSaved && (
          <span className="ca-saved-indicator">
            <FaCheck /> Saved
          </span>
        )}
      </div>
    );
  };

  // ── Offering row ──
  const OfferingRow = ({ o }) => {
    const wl = o.assigned_faculty ? wlMap[o.assigned_faculty] : null;
    const color = wl ? wlColor(wl.remaining, wl.max_weekly_load) : "wl-gray";
    return (
      <div className="ca-offering-row">
        <div className="ca-offering-info">
          <span className="ca-course-code">{o.course_code}</span>
          <span className="ca-course-name">{o.course_name}</span>
          <span className="ca-course-meta">
            {o.credits}cr · {o.weekly_load || o.credits} lec/wk
          </span>
        </div>
        <div className="ca-offering-assign">
          <FacultySelect offering={o} />
          {wl && (
            <span className={`wl-pill ${color}`} style={{ marginLeft: 6 }}>
              {wl.remaining} left
            </span>
          )}
        </div>
      </div>
    );
  };

  return (
    <DashboardLayout>
      <div className="page-head">
        <h1>Course–Faculty Assignment</h1>
        <p>
          Select a program, semester \u0026 section to view courses. Assign faculty
          to each course or upload an Excel for bulk assignment.
        </p>
      </div>

      {/* ── Bulk Upload ── */}
      <BulkUploadCard
        title="Upload Assignment Data"
        endpoint="faculty/eligibility/bulk-upload/"
        useFileUpload
        requiredColumns={["faculty_name", "course_code"]}
        templateFileName="course-assignment-template.xlsx"
        helperText="Excel with columns: faculty_name, course_code. Creates eligibility records + direct assignment when possible."
        templateSampleRow={{
          faculty_name: "Dr. Ritika Mehra",
          course_code: "24AML202",
        }}
        onUploadComplete={() => { loadOfferings(); refreshWorkloads(); }}
      />

      {/* ── Selector Bar ── */}
      <section className="ca-selector-bar">
        <div className="ca-selector-group">
          <label className="form-label">Program</label>
          <select
            className="input"
            value={selProgram}
            onChange={(e) => {
              setSelProgram(e.target.value);
              setSelSemester("");
            }}
          >
            <option value="">Select Program</option>
            {programs.map((p) => (
              <option key={p.id} value={p.id}>
                {p.code} — {p.display_name || p.name}
              </option>
            ))}
          </select>
        </div>

        <div className="ca-selector-group">
          <label className="form-label">Semester</label>
          <select
            className="input"
            value={selSemester}
            onChange={(e) => setSelSemester(e.target.value)}
            disabled={!selProgram}
          >
            <option value="">Select Semester</option>
            {availSemesters.map((s) => (
              <option key={s} value={s}>Semester {s}</option>
            ))}
          </select>
        </div>

        <div className="ca-selector-group">
          <label className="form-label">Section</label>
          {studentGroups.length === 0 ? (
            <div className="ca-no-sections">
              {selProgram && selSemester
                ? "No sections found for this configuration."
                : "Select program & semester first."}
            </div>
          ) : (
            <div className="ca-section-tabs">
              {studentGroups.map((sg) => (
                <button
                  key={sg.id}
                  type="button"
                  className={`ca-section-tab ${String(sg.id) === selSection ? "active" : ""}`}
                  onClick={() => setSelSection(String(sg.id))}
                >
                  {sg.name}
                  <span className="ca-section-strength">{sg.strength} students</span>
                </button>
              ))}
            </div>
          )}
        </div>
      </section>

      {/* ── Course List ── */}
      {selSection && (
        <>
          {/* Search */}
          <div className="ca-search-bar">
            <FaSearch style={{ color: "var(--muted)" }} />
            <input
              className="input"
              placeholder="Search courses or faculty..."
              value={searchQ}
              onChange={(e) => setSearchQ(e.target.value)}
            />
            <span className="ca-search-count">
              {offerings.length} course{offerings.length !== 1 ? "s" : ""} loaded
            </span>
          </div>

          {loading ? (
            <div className="ca-loading">Loading courses...</div>
          ) : grouped.length === 0 ? (
            <div className="ca-empty">
              No course offerings found for this section.
              <br />
              Go to <strong>Sections</strong> page and click "Auto-assign Courses" first.
            </div>
          ) : (
            <div className="ca-groups">
              {grouped.map((group) => {
                const meta = TYPE_META[group.type] || { label: group.type, icon: FaBook, color: "#64748b" };
                const Icon = meta.icon;
                const hasElectives = Object.keys(group.electiveGroups).length > 0;

                return (
                  <section key={group.type} className="ca-type-group">
                    <div className="ca-type-header" style={{ borderLeftColor: meta.color }}>
                      <Icon style={{ color: meta.color, fontSize: 16 }} />
                      <span className="ca-type-label">{meta.label}</span>
                      <span className="ca-type-count">
                        {group.items.length + Object.values(group.electiveGroups).flat().length}
                      </span>
                    </div>

                    {/* Regular items */}
                    {group.items.map((o) => (
                      <OfferingRow key={o.id} o={o} />
                    ))}

                    {/* Elective groups */}
                    {hasElectives && Object.entries(group.electiveGroups).map(
                      ([esg, electives]) => (
                        <div key={esg} className="ca-elective-group">
                          <div className="ca-elective-header">
                            <FaStar style={{ color: meta.color, fontSize: 12 }} />
                            <span>Elective Group: <strong>{esg}</strong></span>
                            <span className="ca-elective-count">
                              {electives.length} choice{electives.length > 1 ? "s" : ""}
                            </span>
                          </div>
                          {electives.map((o) => (
                            <OfferingRow key={o.id} o={o} />
                          ))}
                        </div>
                      )
                    )}
                  </section>
                );
              })}
            </div>
          )}
        </>
      )}

      {/* ── Summary ── */}
      {offerings.length > 0 && (
        <section className="ca-summary-bar">
          <div className="ca-summary-item">
            <strong>{offerings.filter((o) => o.assigned_faculty).length}</strong>
            <span>Assigned</span>
          </div>
          <div className="ca-summary-item ca-summary-warn">
            <strong>{offerings.filter((o) => !o.assigned_faculty).length}</strong>
            <span>Unassigned</span>
          </div>
          <div className="ca-summary-item">
            <strong>{offerings.length}</strong>
            <span>Total</span>
          </div>
        </section>
      )}
    </DashboardLayout>
  );
}

export default CourseAssignmentPage;
