import { useCallback, useEffect, useMemo, useState } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import BulkUploadCard from "../components/BulkUploadCard";
import { asList, extractError, courseDisplayCode } from "../utils/helpers";
import {
  FaUserTie, FaSearch, FaCheck, FaFlask, FaBook, FaStar, FaLightbulb,
  FaExclamationTriangle, FaLink, FaChevronDown, FaChevronRight,
  FaGraduationCap,
} from "react-icons/fa";

/* ── Type metadata ── */
const TYPE_META = {
  PC:  { label: "Program Core",         icon: FaBook,      color: "#6366f1" },
  PE:  { label: "Program Elective",     icon: FaStar,      color: "#f59e0b" },
  OE:  { label: "Open Elective",        icon: FaLightbulb, color: "#14b8a6" },
  PR:  { label: "Practical (Lab)",      icon: FaFlask,     color: "#ef4444" },
  BSC: { label: "Basic Sciences",       icon: FaBook,      color: "#3b82f6" },
  ESC: { label: "Engineering Sci.",     icon: FaBook,      color: "#8b5cf6" },
  HUM: { label: "Humanities",           icon: FaBook,      color: "#ec4899" },
  LS:  { label: "Life Skills",          icon: FaLightbulb, color: "#10b981" },
  VAM: { label: "Value Added",          icon: FaLightbulb, color: "#06b6d4" },
  AEC: { label: "Ability Enhancement",  icon: FaLightbulb, color: "#84cc16" },
  PRJ: { label: "Project",             icon: FaFlask,     color: "#f97316" },
};

/* ── Workload helpers ── */
function wlColor(remaining, max) {
  if (max === 0) return "wl-gray";
  const r = remaining / max;
  if (r <= 0) return "wl-red";
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

  /* Selectors */
  const [selProgram, setSelProgram] = useState("");
  const [selSemester, setSelSemester] = useState("");
  const [selSection, setSelSection] = useState("");

  /* Assignment state */
  const [saving, setSaving] = useState({});
  const [saved, setSaved] = useState({});
  const [searchQ, setSearchQ] = useState("");
  const [expandedTypes, setExpandedTypes] = useState({});

  /* ── Load initial data ── */
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

  /* Workload map */
  const wlMap = useMemo(() => {
    const m = {};
    workloads.forEach((w) => { m[w.id] = w; });
    return m;
  }, [workloads]);

  /* Sorted active faculty */
  const sortedFaculty = useMemo(() =>
    [...faculty].sort((a, b) => a.name.localeCompare(b.name)),
  [faculty]);

  /* Available semesters for selected program */
  const availSemesters = useMemo(() => {
    if (!selProgram) return [];
    const p = programs.find((pr) => String(pr.id) === selProgram);
    if (!p) return [];
    return Array.from({ length: p.total_semesters }, (_, i) => i + 1);
  }, [selProgram, programs]);

  /* ── Load student groups when program+semester changes ── */
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

  /* ── Load offerings when section changes ── */
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

  /* ── Refresh workloads ── */
  const refreshWorkloads = useCallback(async () => {
    const r = await api.get("faculty/faculty/workload/").catch(() => null);
    if (r) setWorkloads(asList(r.data));
  }, []);

  /* ── Assign faculty ── */
  const handleAssign = async (offeringId, facultyId) => {
    // Check workload warning
    if (facultyId) {
      const fac = faculty.find(f => f.id === Number(facultyId));
      const wl = wlMap[Number(facultyId)];
      const offering = offerings.find(o => o.id === offeringId);
      const courseWeekly = offering?.weekly_load || offering?.credits || 0;
      const remaining = wl ? wl.remaining : (fac?.max_weekly_load || 0);

      if (remaining < courseWeekly) {
        const msg = `⚠️ Warning: ${fac?.name || "This faculty"} only has ${remaining} hrs/wk remaining but this course requires ${courseWeekly} hrs/wk.\n\nProceed anyway?`;
        if (!window.confirm(msg)) return;
      }
    }

    setSaving((p) => ({ ...p, [offeringId]: true }));
    try {
      await api.patch(`academics/course-offerings/${offeringId}/`, {
        assigned_faculty: facultyId || null,
      });
      setSaved((p) => ({ ...p, [offeringId]: true }));
      setTimeout(() => setSaved((p) => ({ ...p, [offeringId]: false })), 1500);
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

  /* ── Group offerings by course_type ── */
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
        if (!groups[t].electiveGroups[esg]) groups[t].electiveGroups[esg] = [];
        groups[t].electiveGroups[esg].push(o);
      } else {
        groups[t].items.push(o);
      }
    });

    return typeOrder
      .filter((t) => groups[t])
      .map((t) => {
        const g = groups[t];
        g.items.sort((a, b) => (a.course_name || "").localeCompare(b.course_name || ""));
        Object.values(g.electiveGroups).forEach(arr => arr.sort((a, b) => (a.course_name || "").localeCompare(b.course_name || "")));
        return g;
      });
  }, [offerings, searchQ]);

  const toggleType = (type) => setExpandedTypes((p) => ({ ...p, [type]: !p[type] }));

  // Auto-expand all types when offerings load
  useEffect(() => {
    if (grouped.length > 0) {
      const et = {};
      grouped.forEach((g) => { et[g.type] = true; });
      setExpandedTypes(et);
    }
  }, [offerings]);

  /* Stats */
  const assignedCount = offerings.filter((o) => o.assigned_faculty).length;
  const unassignedCount = offerings.filter((o) => !o.assigned_faculty).length;
  const overloadedFaculty = useMemo(() => {
    return workloads.filter(w => w.remaining < 0);
  }, [workloads]);

  /* ── Faculty dropdown with workload ── */
  const FacultySelect = ({ offering }) => {
    const isSaving = saving[offering.id];
    const isSaved = saved[offering.id];
    const assignedWl = offering.assigned_faculty ? wlMap[offering.assigned_faculty] : null;
    const courseWeekly = offering.weekly_load || offering.credits || 0;
    const isOverload = assignedWl && assignedWl.remaining < 0;

    return (
      <div className="ca-faculty-cell">
        <select
          className={`input ca-faculty-select ${isSaved ? "ca-saved" : ""} ${isOverload ? "ca-overload" : ""}`}
          value={offering.assigned_faculty || ""}
          onChange={(e) => handleAssign(offering.id, e.target.value)}
          disabled={isSaving}
        >
          <option value="">— Unassigned —</option>
          {sortedFaculty.map((f) => {
            const wl = wlMap[f.id];
            const rem = wl ? wl.remaining : f.max_weekly_load;
            const max = wl ? wl.max_weekly_load : f.max_weekly_load;
            const wouldOverload = rem < courseWeekly;
            return (
              <option key={f.id} value={f.id}>
                {wlEmoji(rem, max)} {f.name} ({rem}/{max} hrs left){wouldOverload ? " ⚠️" : ""}
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
        {isOverload && !isSaving && !isSaved && (
          <span className="ca-overload-warn">
            <FaExclamationTriangle /> Overloaded
          </span>
        )}
      </div>
    );
  };

  /* ── Single offering card ── */
  const OfferingCard = ({ o }) => {
    const wl = o.assigned_faculty ? wlMap[o.assigned_faculty] : null;
    const isOverload = wl && wl.remaining < 0;
    const dispCode = courseDisplayCode(o.course_display_code || o.course_code);

    return (
      <div className={`ca-card ${isOverload ? "ca-card-warn" : ""} ${o.assigned_faculty ? "ca-card-assigned" : ""}`}>
        <div className="ca-card-header">
          <div className="ca-card-title">{o.course_name}</div>
          <span className="ca-card-type-badge" style={{ color: TYPE_META[o.course_type]?.color || "#64748b" }}>
            {o.course_type}
          </span>
        </div>

        <div className="ca-card-code">{dispCode}</div>

        <div className="ca-card-assign">
          <FacultySelect offering={o} />
        </div>
      </div>
    );
  };

  const selProgramObj = programs.find(p => String(p.id) === selProgram);

  return (
    <DashboardLayout>
      {/* Header */}
      <div className="sec-page-header">
        <div>
          <h1 className="sec-page-title">Course–Faculty Assignments</h1>
          <p className="sec-page-sub">
            Assign faculty to course offerings. Select a program, semester &amp; section to manage assignments.
          </p>
        </div>
      </div>

      {/* Bulk Upload */}
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

      {/* Selector Panel */}
      <div className="sec-form-panel" style={{ marginBottom: 16 }}>
        <div className="sec-form-header">
          <h3><FaGraduationCap style={{ marginRight: 8, color: "var(--brand)" }} />Select Section</h3>
        </div>
        <div className="ca-selector-grid">
          <div className="sec-field">
            <label>Program</label>
            <select
              value={selProgram}
              onChange={(e) => { setSelProgram(e.target.value); setSelSemester(""); }}
            >
              <option value="">Choose program</option>
              {[...programs].sort((a, b) => (a.display_name || a.name || "").localeCompare(b.display_name || b.name || "")).map((p) => (
                <option key={p.id} value={p.id}>{p.display_name || p.name}</option>
              ))}
            </select>
          </div>

          <div className="sec-field">
            <label>Semester</label>
            <select
              value={selSemester}
              onChange={(e) => setSelSemester(e.target.value)}
              disabled={!selProgram}
            >
              <option value="">{selProgram ? "Choose semester" : "Select program first"}</option>
              {availSemesters.map((s) => (
                <option key={s} value={s}>Semester {s}</option>
              ))}
            </select>
          </div>

          <div className="sec-field sec-field-wide">
            <label>Section</label>
            {studentGroups.length === 0 ? (
              <div style={{ fontSize: 13, color: "var(--muted)", padding: "10px 0" }}>
                {selProgram && selSemester
                  ? "No sections found."
                  : "Select program & semester first."}
              </div>
            ) : (
              <div className="ca-section-chips">
                {studentGroups.map((sg) => (
                  <button
                    key={sg.id}
                    type="button"
                    className={`ca-section-chip ${String(sg.id) === selSection ? "active" : ""}`}
                    onClick={() => setSelSection(String(sg.id))}
                  >
                    {sg.name}
                    <span className="ca-chip-strength">{sg.strength}</span>
                  </button>
                ))}
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Main Content */}
      {selSection && (
        <>
          {/* Summary Strip */}
          <div className="sec-summary-strip">
            <div className="sec-summary-item">
              <FaBook />
              <span><strong>{offerings.length}</strong> Offerings</span>
            </div>
            <div className="sec-summary-item" style={{ color: "var(--success)" }}>
              <FaCheck />
              <span><strong>{assignedCount}</strong> Assigned</span>
            </div>
            {unassignedCount > 0 && (
              <div className="sec-summary-item" style={{ color: "var(--warning)" }}>
                <FaExclamationTriangle />
                <span><strong>{unassignedCount}</strong> Unassigned</span>
              </div>
            )}
            {overloadedFaculty.length > 0 && (
              <div className="sec-summary-item" style={{ color: "var(--danger)" }}>
                <FaExclamationTriangle />
                <span><strong>{overloadedFaculty.length}</strong> Overloaded</span>
              </div>
            )}
            <div style={{ marginLeft: "auto" }}>
              <div className="pdc-search-wrap">
                <FaSearch className="pdc-search-icon" />
                <input
                  className="input pdc-search-input"
                  placeholder="Search courses..."
                  value={searchQ}
                  onChange={(e) => setSearchQ(e.target.value)}
                />
              </div>
            </div>
          </div>

          {loading ? (
            <div className="sec-loading">
              <div className="sec-loading-spinner" />
              Loading courses...
            </div>
          ) : grouped.length === 0 ? (
            <div className="sec-empty">
              <FaLink className="sec-empty-icon" />
              <h3>No course offerings found</h3>
              <p>Go to the Sections page and click "Auto-assign Courses" first.</p>
            </div>
          ) : (
            <div className="sec-hierarchy">
              {grouped.map((group) => {
                const meta = TYPE_META[group.type] || { label: group.type, icon: FaBook, color: "#64748b" };
                const Icon = meta.icon;
                const totalItems = group.items.length + Object.values(group.electiveGroups).flat().length;
                const isExpanded = expandedTypes[group.type];

                return (
                  <div key={group.type} className="sec-program-block">
                    <button
                      className="sec-program-header"
                      onClick={() => toggleType(group.type)}
                      style={{ borderLeft: `3px solid ${meta.color}` }}
                    >
                      <div className="sec-program-left">
                        {isExpanded ? <FaChevronDown size={12} /> : <FaChevronRight size={12} />}
                        <div className="sec-program-icon" style={{ background: `${meta.color}18`, color: meta.color }}>
                          <Icon />
                        </div>
                        <div>
                          <span className="sec-program-name">{meta.label}</span>
                        </div>
                      </div>
                      <div className="sec-program-meta">
                        <span className="sec-meta-badge">{totalItems} courses</span>
                        {group.items.filter(o => !o.assigned_faculty).length +
                         Object.values(group.electiveGroups).flat().filter(o => !o.assigned_faculty).length > 0 && (
                          <span className="sec-meta-badge" style={{ background: "var(--warning-light)", color: "var(--warning)" }}>
                            {group.items.filter(o => !o.assigned_faculty).length +
                             Object.values(group.electiveGroups).flat().filter(o => !o.assigned_faculty).length} unassigned
                          </span>
                        )}
                      </div>
                    </button>

                    {isExpanded && (
                      <div className="sec-years-container">
                        {/* Regular items */}
                        {group.items.length > 0 && (
                          <div className="ca-cards-grid">
                            {group.items.map((o) => (
                              <OfferingCard key={o.id} o={o} />
                            ))}
                          </div>
                        )}

                        {/* Elective groups */}
                        {Object.entries(group.electiveGroups).map(([esg, electives]) => (
                          <div key={esg} className="ca-elective-block">
                            <div className="ca-elective-banner">
                              <FaStar style={{ color: meta.color, fontSize: 13 }} />
                              <span>Elective Group: <strong>{courseDisplayCode(esg)}</strong></span>
                              <span className="ca-elective-cnt">{electives.length} choices</span>
                            </div>
                            <div className="ca-cards-grid">
                              {electives.map((o) => (
                                <OfferingCard key={o.id} o={o} />
                              ))}
                            </div>
                          </div>
                        ))}
                      </div>
                    )}
                  </div>
                );
              })}
            </div>
          )}
        </>
      )}
    </DashboardLayout>
  );
}

export default CourseAssignmentPage;
