import { useCallback, useEffect, useState, useMemo } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import BulkUploadCard from "../components/BulkUploadCard";
import { toBoolean, toNumber } from "../utils/spreadsheet";
import { asList, extractError } from "../utils/helpers";
import {
  FaChevronDown,
  FaChevronUp,
  FaTrash,
  FaUserTie,
  FaEdit,
  FaTimes,
  FaSearch,
  FaGraduationCap,
  FaBookOpen,
  FaArrowLeft,
  FaSortAmountDown,
  FaBan,
  FaCheck,
} from "react-icons/fa";

/* ═══════════════════════════════════════════════════════════════
   Constants
   ═══════════════════════════════════════════════════════════════ */
const DAYS = [
  { key: "MON", label: "Monday" },
  { key: "TUE", label: "Tuesday" },
  { key: "WED", label: "Wednesday" },
  { key: "THU", label: "Thursday" },
  { key: "FRI", label: "Friday" },
];

const ROLE_DEFAULTS = {
  PVC:      { max_weekly_load: 4,  max_lectures_per_day: 2, max_consecutive_lectures: 1 },
  DEAN:     { max_weekly_load: 6,  max_lectures_per_day: 2, max_consecutive_lectures: 1 },
  HOD:      { max_weekly_load: 12, max_lectures_per_day: 3, max_consecutive_lectures: 2 },
  REGULAR:  { max_weekly_load: 18, max_lectures_per_day: 4, max_consecutive_lectures: 2 },
  VISITING: { max_weekly_load: 8,  max_lectures_per_day: 3, max_consecutive_lectures: 2 },
};

const ROLE_LABELS = {
  PVC: "Pro Vice Chancellor",
  DEAN: "Dean of School",
  HOD: "Head of Department",
  REGULAR: "Regular Faculty",
  VISITING: "Visiting / Contractual",
};

const SLOTS = [1, 2, 3, 4, 5, 6];
const SLOT_TIMES = {
  1: "09:40–10:35", 2: "10:35–11:30", 3: "11:30–12:25",
  4: "12:25–13:20", 5: "14:15–15:10", 6: "15:10–16:05",
};

const INITIAL_FORM = {
  name: "",
  employee_id: "",
  designation: "",
  role: "REGULAR",
  department: "",
  max_lectures_per_day: 4,
  max_consecutive_lectures: 2,
  max_weekly_load: 18,
};

function buildInitialAvailability() {
  const avail = {};
  DAYS.forEach((d) => {
    avail[d.key] = { allDay: true, slots: {} };
    SLOTS.forEach((s) => { avail[d.key].slots[s] = true; });
  });
  return avail;
}

/* ═══════════════════════════════════════════════════════════════
   Faculty Card — displayed in the right panel
   ═══════════════════════════════════════════════════════════════ */
function FacultyCard({ fac, onEdit, onDelete, onClick }) {
  return (
    <div className="fac-card" onClick={onClick} style={{ cursor: "pointer" }}>
      {/* Avatar + Name */}
      <div className="fac-card-top">
        <div className="fac-card-avatar">
          {fac.name.charAt(0).toUpperCase()}
        </div>
        <div className="fac-card-info">
          <div className="fac-card-name">{fac.name}</div>
          <div className="fac-card-empid">{fac.employee_id}</div>
        </div>
      </div>

      {/* Badges row */}
      <div className="fac-card-badges">
        {fac.designation && (
          <span className="fac-badge fac-badge-desg">{fac.designation}</span>
        )}
        <span className={`fac-badge fac-badge-role role-${fac.role.toLowerCase()}`}>
          {fac.role}
        </span>
      </div>

      {/* Workload row */}
      <div className="fac-card-meta">
        <span title="Max lectures per day">{fac.max_lectures_per_day}/day</span>
        <span className="fac-card-dot">·</span>
        <span title="Max weekly load">{fac.max_weekly_load}/wk</span>
      </div>

      {/* Actions */}
      <div className="fac-card-actions">
        <button className="action-btn" onClick={(e) => { e.stopPropagation(); onEdit(fac); }} title="Edit">
          <FaEdit style={{ color: "#3b82f6" }} />
        </button>
        <button className="action-btn danger" onClick={(e) => { e.stopPropagation(); onDelete(fac.id); }} title="Delete">
          <FaTrash />
        </button>
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Exclusion Configurator — Program → Semester → Courses
   All courses are teachable by default. Click to EXCLUDE.
   ═══════════════════════════════════════════════════════════════ */
function EligibilityConfigurator({
  programs, courses,
  excludedSubjects, toggleExclusion,
  excludedPrograms, toggleProgExcl,
  excludedSemesters, toggleSemExcl,
}) {
  const [expandedProg, setExpandedProg] = useState(null);
  const [expandedSem, setExpandedSem] = useState(null);

  // Group courses by program → semester
  const tree = useMemo(() => {
    const map = {};
    courses.forEach((c) => {
      const pid = c.program;
      if (!pid) return;
      if (!map[pid]) map[pid] = {};
      const sem = c.semester || 0;
      if (!map[pid][sem]) map[pid][sem] = [];
      map[pid][sem].push(c);
    });
    return map;
  }, [courses]);

  const toggleProgView = (pid) => {
    setExpandedProg(expandedProg === pid ? null : pid);
    setExpandedSem(null);
  };

  const toggleSemView = (sem) => {
    setExpandedSem(expandedSem === sem ? null : sem);
  };

  // Count total exclusions (all three levels)
  const exclCourseCount = Object.keys(excludedSubjects).filter((k) => excludedSubjects[k]).length;
  const exclProgCount = Object.keys(excludedPrograms).filter((k) => excludedPrograms[k]).length;
  const exclSemCount = Object.keys(excludedSemesters).filter((k) => excludedSemesters[k]).length;
  const totalExcl = exclCourseCount + exclProgCount + exclSemCount;

  return (
    <div className="elig-config">
      <div className="elig-header-bar">
        <FaBookOpen style={{ color: "var(--brand)", flexShrink: 0 }} />
        <span className="elig-header-text">
          {totalExcl === 0
            ? "Can teach all courses (no exclusions)"
            : `${totalExcl} exclusion${totalExcl > 1 ? "s" : ""} configured`}
        </span>
      </div>

      <div className="elig-prog-list">
        {programs
          .filter((p) => tree[p.id])
          .sort((a, b) => (a.display_name || a.name || "").localeCompare(b.display_name || b.name || ""))
          .map((prog) => {
            const isProgExcluded = !!excludedPrograms[prog.id];
            const isExpanded = expandedProg === prog.id;
            const sems = Object.keys(tree[prog.id] || {}).map(Number).sort((a, b) => a - b);
            const progCourses = Object.values(tree[prog.id] || {}).flat();
            const courseExclInProg = progCourses.filter((c) => excludedSubjects[c.id]).length;
            const semExclInProg = sems.filter(s => excludedSemesters[`${prog.id}-${s}`]).length;

            return (
              <div key={prog.id} className="elig-prog-item">
                <div
                  className={`elig-prog-header ${isExpanded ? "active" : ""} ${isProgExcluded ? "prog-excluded" : ""}`}
                  onClick={() => toggleProgView(prog.id)}
                >
                  {/* Program-level checkbox */}
                  <label
                    className={`elig-level-check ${isProgExcluded ? "excluded" : ""}`}
                    onClick={(e) => e.stopPropagation()}
                    title={isProgExcluded ? "Unexclude entire program" : "Exclude entire program"}
                  >
                    <input type="checkbox" checked={isProgExcluded}
                      onChange={() => toggleProgExcl(prog.id)} />
                    <span className="elig-check-icon">{isProgExcluded ? "✕" : "✓"}</span>
                  </label>
                  <FaGraduationCap className="elig-prog-icon" />
                  <span className={`elig-prog-name ${isProgExcluded ? "excl-strike" : ""}`}>
                    {prog.display_name || prog.name}
                  </span>
                  {isProgExcluded && <span className="elig-prog-count excl">Excluded</span>}
                  {!isProgExcluded && (courseExclInProg + semExclInProg) > 0 && (
                    <span className="elig-prog-count excl">{courseExclInProg + semExclInProg}</span>
                  )}
                  {isExpanded ? <FaChevronUp className="elig-chevron" /> : <FaChevronDown className="elig-chevron" />}
                </div>

                {isExpanded && (
                  <div className="elig-sem-list">
                    {isProgExcluded && (
                      <div className="elig-level-notice">
                        <FaBan style={{ color: "#ef4444" }} />
                        Entire program excluded — all semesters and courses blocked.
                      </div>
                    )}
                    {sems.map((sem) => {
                      const semKey = `${prog.id}-${sem}`;
                      const isSemExcluded = !!excludedSemesters[semKey];
                      const semCourses = tree[prog.id]?.[sem] || [];
                      const semCourseExcl = semCourses.filter((c) => excludedSubjects[c.id]).length;
                      const isSemExpanded = expandedSem === semKey;
                      const isBlockedByProg = isProgExcluded;
                      
                      return (
                        <div key={sem} className="elig-sem-item">
                          <div
                            className={`elig-sem-header ${isSemExpanded ? "active" : ""} ${(isSemExcluded || isBlockedByProg) ? "sem-excluded" : ""}`}
                            onClick={() => toggleSemView(semKey)}
                          >
                            <label
                              className={`elig-level-check small ${(isSemExcluded || isBlockedByProg) ? "excluded" : ""}`}
                              onClick={(e) => e.stopPropagation()}
                              title={isSemExcluded ? "Unexclude semester" : "Exclude semester"}
                            >
                              <input type="checkbox"
                                checked={isSemExcluded || isBlockedByProg}
                                disabled={isBlockedByProg}
                                onChange={() => toggleSemExcl(prog.id, sem)} />
                              <span className="elig-check-icon">{(isSemExcluded || isBlockedByProg) ? "✕" : "✓"}</span>
                            </label>
                            <span className="elig-sem-badge">S{sem}</span>
                            <span className={`elig-sem-label ${(isSemExcluded || isBlockedByProg) ? "excl-strike" : ""}`}>
                              Semester {sem}
                              <span className="elig-sem-cnt">({semCourses.length} courses)</span>
                            </span>
                            {(isSemExcluded || isBlockedByProg) && <span className="elig-prog-count excl" style={{ fontSize: 9 }}>Excluded</span>}
                            {!isSemExcluded && !isBlockedByProg && semCourseExcl > 0 && (
                              <span className="elig-prog-count excl">{semCourseExcl}</span>
                            )}
                          </div>

                          {isSemExpanded && (
                            <div className="elig-course-grid">
                              {semCourses.map((c) => {
                                const isCourseBlocked = isBlockedByProg || isSemExcluded;
                                const isCourseExcluded = isCourseBlocked || !!excludedSubjects[c.id];
                                return (
                                  <label
                                    key={c.id}
                                    className={`elig-course-chip ${isCourseExcluded ? "excluded" : ""}`}
                                    style={isCourseBlocked ? { opacity: 0.5, pointerEvents: "none" } : {}}
                                  >
                                    <input type="checkbox"
                                      checked={!!excludedSubjects[c.id]}
                                      disabled={isCourseBlocked}
                                      onChange={() => toggleExclusion(c.id)} />
                                    <code>{c.display_code || c.code}</code>
                                    <span>{c.name}</span>
                                  </label>
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
            );
          })}
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Faculty Detail View — full page detail with courses
   ═══════════════════════════════════════════════════════════════ */
function FacultyDetailView({ fac, programs, courses, exclusions, progExclusions, semExclusions, availabilities, onBack }) {
  const [expandedProg, setExpandedProg] = useState(null);

  // Build exclusion sets from DB records
  const excludedCourseIds = useMemo(() => {
    const set = new Set();
    exclusions.filter(e => e.faculty === fac.id).forEach(e => {
      set.add(e.course?.id || e.course);
    });
    return set;
  }, [exclusions, fac.id]);

  const excludedProgIds = useMemo(() => {
    const set = new Set();
    progExclusions.filter(e => e.faculty === fac.id).forEach(e => set.add(e.program));
    return set;
  }, [progExclusions, fac.id]);

  const excludedSemKeys = useMemo(() => {
    const set = new Set();
    semExclusions.filter(e => e.faculty === fac.id).forEach(e => set.add(`${e.program}-${e.semester}`));
    return set;
  }, [semExclusions, fac.id]);

  // Group courses by program → semester
  const courseTree = useMemo(() => {
    const map = {};
    courses.forEach((c) => {
      const pid = c.program;
      if (!pid) return;
      if (!map[pid]) map[pid] = {};
      const sem = c.semester || 0;
      if (!map[pid][sem]) map[pid][sem] = [];
      map[pid][sem].push(c);
    });
    return map;
  }, [courses]);

  // Build availability summary
  const availSummary = useMemo(() => {
    const facAvails = availabilities.filter(a => a.faculty === fac.id);
    if (facAvails.length === 0) return "Available all day, every day (default)";
    const daySlots = {};
    facAvails.forEach(a => {
      if (!daySlots[a.day]) daySlots[a.day] = [];
      for (let s = a.start_slot; s < a.end_slot; s++) daySlots[a.day].push(s);
    });
    return Object.entries(daySlots)
      .map(([day, slots]) => `${day}: Slots ${slots.sort().join(", ")}`)
      .join("  ·  ");
  }, [availabilities, fac.id]);

  const canTeachCount = courses.length - excludedCourseIds.size;

  return (
    <div className="fac-detail-view">
      {/* Header */}
      <button className="fac-detail-back" onClick={onBack}>
        <FaArrowLeft /> Back to Faculty List
      </button>

      {/* Profile card */}
      <div className="fac-detail-profile">
        <div className="fac-detail-avatar">
          {fac.name.charAt(0).toUpperCase()}
        </div>
        <div className="fac-detail-info">
          <h2 className="fac-detail-name">{fac.name}</h2>
          <p className="fac-detail-empid">{fac.employee_id}</p>
          <div className="fac-card-badges" style={{ marginTop: 6 }}>
            {fac.designation && <span className="fac-badge fac-badge-desg">{fac.designation}</span>}
            <span className={`fac-badge fac-badge-role role-${fac.role.toLowerCase()}`}>
              {ROLE_LABELS[fac.role] || fac.role}
            </span>
          </div>
        </div>
      </div>

      {/* Stats row */}
      <div className="fac-detail-stats">
        <div className="fac-detail-stat">
          <div className="fac-detail-stat-val">{fac.max_lectures_per_day}</div>
          <div className="fac-detail-stat-lbl">Max / Day</div>
        </div>
        <div className="fac-detail-stat">
          <div className="fac-detail-stat-val">{fac.max_consecutive_lectures || 2}</div>
          <div className="fac-detail-stat-lbl">Max Consec.</div>
        </div>
        <div className="fac-detail-stat">
          <div className="fac-detail-stat-val">{fac.max_weekly_load}</div>
          <div className="fac-detail-stat-lbl">Max / Week</div>
        </div>
        <div className="fac-detail-stat">
          <div className="fac-detail-stat-val" style={{ color: "#059669" }}>{canTeachCount}</div>
          <div className="fac-detail-stat-lbl">Can Teach</div>
        </div>
        <div className="fac-detail-stat">
          <div className="fac-detail-stat-val" style={{ color: "#ef4444" }}>{excludedCourseIds.size}</div>
          <div className="fac-detail-stat-lbl">Excluded</div>
        </div>
      </div>

      {/* Availability summary */}
      <div className="fac-detail-section">
        <h4><FaBookOpen style={{ marginRight: 6, color: "var(--brand)" }} />Availability</h4>
        <p className="fac-detail-avail-text">{availSummary}</p>
      </div>

      {/* Courses — grouped by program → semester */}
      <div className="fac-detail-section">
        <h4><FaGraduationCap style={{ marginRight: 6, color: "var(--brand)" }} />Course Eligibility</h4>
        {excludedCourseIds.size === 0 && excludedProgIds.size === 0 && excludedSemKeys.size === 0 && (
          <p className="fac-detail-avail-text">
            <FaCheck style={{ color: "#059669", marginRight: 4 }} />
            Can teach all {courses.length} courses (no exclusions configured)
          </p>
        )}

        <div className="fac-detail-prog-list">
          {programs
            .filter(p => courseTree[p.id])
            .sort((a, b) => (a.display_name || a.name || "").localeCompare(b.display_name || b.name || ""))
            .map(prog => {
              const isExp = expandedProg === prog.id;
              const isProgExcl = excludedProgIds.has(prog.id);
              const sems = Object.keys(courseTree[prog.id] || {}).map(Number).sort((a, b) => a - b);
              const progCourses = Object.values(courseTree[prog.id] || {}).flat();
              const progExclCount = isProgExcl ? progCourses.length : progCourses.filter(c => excludedCourseIds.has(c.id)).length;

              return (
                <div key={prog.id} className="elig-prog-item">
                  <div
                    className={`elig-prog-header ${isExp ? "active" : ""} ${isProgExcl ? "prog-excluded" : ""}`}
                    onClick={() => setExpandedProg(isExp ? null : prog.id)}
                  >
                    <FaGraduationCap className="elig-prog-icon" />
                    <span className={`elig-prog-name ${isProgExcl ? "excl-strike" : ""}`}>{prog.display_name || prog.name}</span>
                    {isProgExcl && <span className="elig-prog-count excl">Program Excluded</span>}
                    {!isProgExcl && progExclCount > 0 && <span className="elig-prog-count excl">{progExclCount}</span>}
                    {isExp ? <FaChevronUp className="elig-chevron" /> : <FaChevronDown className="elig-chevron" />}
                  </div>

                  {isExp && (
                    <div className="elig-sem-list">
                      {isProgExcl && (
                        <div className="elig-level-notice">
                          <FaBan style={{ color: "#ef4444" }} /> Entire program excluded
                        </div>
                      )}
                      {sems.map(sem => {
                        const semCourses = courseTree[prog.id]?.[sem] || [];
                        const isSemExcl = excludedSemKeys.has(`${prog.id}-${sem}`);
                        return (
                          <div key={sem} className="elig-sem-item">
                            <div className={`elig-sem-header active ${(isSemExcl || isProgExcl) ? "sem-excluded" : ""}`} style={{ cursor: "default" }}>
                              <span className="elig-sem-badge">S{sem}</span>
                              <span className={`elig-sem-label ${(isSemExcl || isProgExcl) ? "excl-strike" : ""}`}>
                                Semester {sem}
                                <span className="elig-sem-cnt">({semCourses.length} courses)</span>
                              </span>
                              {(isSemExcl && !isProgExcl) && <span className="elig-prog-count excl" style={{ fontSize: 9 }}>Sem Excluded</span>}
                            </div>
                            <div className="elig-course-grid">
                              {semCourses.map(c => {
                                const isExcl = isProgExcl || isSemExcl || excludedCourseIds.has(c.id);
                                return (
                                  <div
                                    key={c.id}
                                    className={`elig-course-chip ${isExcl ? "excluded" : ""}`}
                                    style={{ cursor: "default", ...(isProgExcl || isSemExcl ? { opacity: 0.5 } : {}) }}
                                  >
                                    {isExcl
                                      ? <FaBan style={{ color: "#ef4444", fontSize: 8, flexShrink: 0 }} />
                                      : <FaCheck style={{ color: "#059669", fontSize: 8, flexShrink: 0 }} />
                                    }
                                    <code>{c.display_code || c.code}</code>
                                    <span>{c.name}</span>
                                  </div>
                                );
                              })}
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
      </div>
    </div>
  );
}

/* ═══════════════════════════════════════════════════════════════
   Main Page
   ═══════════════════════════════════════════════════════════════ */
function FacultyPage() {
  const [faculty, setFaculty] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [programs, setPrograms] = useState([]);
  const [courses, setCourses] = useState([]);
  const [availabilityData, setAvailabilityData] = useState([]);
  const [eligibilityData, setEligibilityData] = useState([]);
  const [progExclData, setProgExclData] = useState([]);
  const [semExclData, setSemExclData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [search, setSearch] = useState("");

  const [form, setForm] = useState(INITIAL_FORM);
  const [showAvailability, setShowAvailability] = useState(false);
  const [showEligibility, setShowEligibility] = useState(false);
  const [availability, setAvailability] = useState(buildInitialAvailability());
  const [excludedSubjects, setExcludedSubjects] = useState({});
  const [excludedPrograms, setExcludedPrograms] = useState({});
  const [excludedSemesters, setExcludedSemesters] = useState({});
  const [editId, setEditId] = useState(null);
  const [viewingFaculty, setViewingFaculty] = useState(null);
  const [sortBy, setSortBy] = useState("az");

  const loadAll = useCallback(async () => {
    try {
      setLoading(true);
      const [facR, deptR, progR, courseR, availR, eligR, progExclR, semExclR] = await Promise.all([
        api.get("faculty/faculty/").catch(() => null),
        api.get("academics/departments/").catch(() => null),
        api.get("academics/programs/").catch(() => null),
        api.get("academics/courses/").catch(() => null),
        api.get("faculty/teacher-availability/").catch(() => null),
        api.get("faculty/faculty-subject-eligibility/").catch(() => null),
        api.get("faculty/program-exclusions/").catch(() => null),
        api.get("faculty/semester-exclusions/").catch(() => null),
      ]);
      setFaculty(facR ? asList(facR.data) : []);
      setDepartments(deptR ? asList(deptR.data) : []);
      setPrograms(progR ? asList(progR.data) : []);
      setCourses(courseR ? asList(courseR.data) : []);
      setAvailabilityData(availR ? asList(availR.data) : []);
      setEligibilityData(eligR ? asList(eligR.data) : []);
      setProgExclData(progExclR ? asList(progExclR.data) : []);
      setSemExclData(semExclR ? asList(semExclR.data) : []);
    } catch (err) {
      console.error("Failed to load data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  /* ── Role change → auto-fill workload ── */
  const handleRoleChange = (role) => {
    const defaults = ROLE_DEFAULTS[role] || ROLE_DEFAULTS.REGULAR;
    setForm((p) => ({
      ...p,
      role,
      max_lectures_per_day: defaults.max_lectures_per_day,
      max_consecutive_lectures: defaults.max_consecutive_lectures,
      max_weekly_load: defaults.max_weekly_load,
    }));
  };

  /* ── Availability toggles ── */
  const toggleAllDay = (dayKey) => {
    setAvailability((prev) => {
      const newAllDay = !prev[dayKey].allDay;
      const newSlots = {};
      SLOTS.forEach((s) => { newSlots[s] = newAllDay; });
      return { ...prev, [dayKey]: { allDay: newAllDay, slots: newSlots } };
    });
  };

  const toggleSlot = (dayKey, slot) => {
    setAvailability((prev) => {
      const newSlots = { ...prev[dayKey].slots, [slot]: !prev[dayKey].slots[slot] };
      const allChecked = SLOTS.every((s) => newSlots[s]);
      return { ...prev, [dayKey]: { allDay: allChecked, slots: newSlots } };
    });
  };

  /* ── Subject exclusion toggle ── */
  const toggleExclusion = (courseId) => {
    setExcludedSubjects((prev) => {
      const copy = { ...prev };
      if (copy[courseId]) delete copy[courseId];
      else copy[courseId] = true;
      return copy;
    });
  };

  /* ── Program exclusion toggle ── */
  const toggleProgExcl = (progId) => {
    setExcludedPrograms((prev) => {
      const copy = { ...prev };
      if (copy[progId]) delete copy[progId];
      else copy[progId] = true;
      return copy;
    });
  };

  /* ── Semester exclusion toggle ── */
  const toggleSemExcl = (progId, sem) => {
    const key = `${progId}-${sem}`;
    setExcludedSemesters((prev) => {
      const copy = { ...prev };
      if (copy[key]) delete copy[key];
      else copy[key] = true;
      return copy;
    });
  };

  /* ── Submit ── */
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(""); setSuccess(""); setSubmitting(true);

    try {
      const facPayload = {
        name: form.name,
        employee_id: form.employee_id,
        designation: form.designation,
        role: form.role,
        max_lectures_per_day:     Number(form.max_lectures_per_day),
        max_consecutive_lectures: Number(form.max_consecutive_lectures),
        max_weekly_load:          Number(form.max_weekly_load),
        is_active: true,
      };
      if (form.department) facPayload.department = Number(form.department);

      let facultyId = editId;

      if (editId) {
        await api.patch(`faculty/faculty/${editId}/`, facPayload);
        await Promise.all([
          ...availabilityData.filter(a => a.faculty === editId).map(a => api.delete(`faculty/teacher-availability/${a.id}/`)),
          ...eligibilityData.filter(e => e.faculty === editId).map(e => api.delete(`faculty/faculty-subject-eligibility/${e.id}/`)),
          ...progExclData.filter(e => e.faculty === editId).map(e => api.delete(`faculty/program-exclusions/${e.id}/`)),
          ...semExclData.filter(e => e.faculty === editId).map(e => api.delete(`faculty/semester-exclusions/${e.id}/`)),
        ]);
      } else {
        const facResp = await api.post("faculty/faculty/", facPayload);
        facultyId = facResp.data.id;
      }

      // Save availability
      const availPromises = [];
      DAYS.forEach((d) => {
        const activeSlots = SLOTS.filter((s) => availability[d.key].slots[s]);
        if (activeSlots.length === 0) return;
        let blockStart = activeSlots[0], blockEnd = activeSlots[0];
        for (let i = 1; i < activeSlots.length; i++) {
          if (activeSlots[i] === blockEnd + 1) {
            blockEnd = activeSlots[i];
          } else {
            availPromises.push(api.post("faculty/teacher-availability/", {
              faculty: facultyId, day: d.key, start_slot: blockStart, end_slot: blockEnd + 1,
            }));
            blockStart = activeSlots[i]; blockEnd = activeSlots[i];
          }
        }
        availPromises.push(api.post("faculty/teacher-availability/", {
          faculty: facultyId, day: d.key, start_slot: blockStart, end_slot: blockEnd + 1,
        }));
      });
      await Promise.all(availPromises);

      // Save exclusions (courses this faculty CANNOT teach)
      const excludedIds = Object.keys(excludedSubjects).filter((id) => excludedSubjects[id]);
      if (excludedIds.length > 0) {
        await Promise.all(
          excludedIds.map((courseId) =>
            api.post("faculty/faculty-subject-eligibility/", {
              faculty: facultyId, course: Number(courseId), priority_weight: 1,
            })
          )
        );
      }

      // Save program exclusions
      const progExclIds = Object.keys(excludedPrograms).filter(id => excludedPrograms[id]);
      if (progExclIds.length > 0) {
        await Promise.all(
          progExclIds.map(progId =>
            api.post("faculty/program-exclusions/", {
              faculty: facultyId, program: Number(progId),
            })
          )
        );
      }

      // Save semester exclusions
      const semExclKeys = Object.keys(excludedSemesters).filter(k => excludedSemesters[k]);
      if (semExclKeys.length > 0) {
        await Promise.all(
          semExclKeys.map(key => {
            const [progId, sem] = key.split("-");
            return api.post("faculty/semester-exclusions/", {
              faculty: facultyId, program: Number(progId), semester: Number(sem),
            });
          })
        );
      }

      setForm(INITIAL_FORM);
      setAvailability(buildInitialAvailability());
      setExcludedSubjects({});
      setExcludedPrograms({});
      setExcludedSemesters({});
      setShowAvailability(false);
      setShowEligibility(false);
      setEditId(null);
      setSuccess(editId ? "Faculty updated successfully." : "Faculty registered successfully.");
      loadAll();
    } catch (err) {
      setError(extractError(err, "Failed to save faculty."));
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (fac) => {
    setEditId(fac.id);
    setForm({
      name: fac.name,
      employee_id: fac.employee_id,
      designation: fac.designation || "",
      role: fac.role,
      department: fac.department || "",
      max_lectures_per_day: fac.max_lectures_per_day,
      max_consecutive_lectures: fac.max_consecutive_lectures,
      max_weekly_load: fac.max_weekly_load,
    });

    // Reconstruct availability
    const newAvail = buildInitialAvailability();
    const facAvails = availabilityData.filter(a => a.faculty === fac.id);
    if (facAvails.length > 0) {
      DAYS.forEach(d => {
        newAvail[d.key].allDay = false;
        SLOTS.forEach(s => newAvail[d.key].slots[s] = false);
      });
      facAvails.forEach(a => {
        for (let s = a.start_slot; s < a.end_slot; s++) newAvail[a.day].slots[s] = true;
      });
      DAYS.forEach(d => { newAvail[d.key].allDay = SLOTS.every(s => newAvail[d.key].slots[s]); });
    }
    setAvailability(newAvail);

    // Reconstruct course exclusions
    const newExcluded = {};
    eligibilityData.filter(e => e.faculty === fac.id).forEach(e => {
      newExcluded[e.course?.id || e.course] = true;
    });
    setExcludedSubjects(newExcluded);

    // Reconstruct program exclusions
    const newProgExcl = {};
    progExclData.filter(e => e.faculty === fac.id).forEach(e => {
      newProgExcl[e.program] = true;
    });
    setExcludedPrograms(newProgExcl);

    // Reconstruct semester exclusions
    const newSemExcl = {};
    semExclData.filter(e => e.faculty === fac.id).forEach(e => {
      newSemExcl[`${e.program}-${e.semester}`] = true;
    });
    setExcludedSemesters(newSemExcl);

    setShowAvailability(false);
    setShowEligibility(false);
    setError(""); setSuccess("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const cancelEdit = () => {
    setEditId(null);
    setForm(INITIAL_FORM);
    setAvailability(buildInitialAvailability());
    setExcludedSubjects({});
    setExcludedPrograms({});
    setExcludedSemesters({});
    setShowAvailability(false);
    setShowEligibility(false);
    setError(""); setSuccess("");
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this faculty member?")) return;
    try {
      await api.delete(`faculty/faculty/${id}/`);
      loadAll();
    } catch (err) {
      setError(extractError(err, "Failed to delete faculty."));
    }
  };

  /* ── Sort + Group faculty for display ── */
  const sortedFaculty = useMemo(() => {
    const q = search.toLowerCase();
    const filtered = q
      ? faculty.filter(
          (f) =>
            (f.name || "").toLowerCase().includes(q) ||
            (f.employee_id || "").toLowerCase().includes(q) ||
            (f.designation || "").toLowerCase().includes(q) ||
            (f.department_name || "").toLowerCase().includes(q)
        )
      : [...faculty];

    // Apply sort
    const cmp = {
      az: (a, b) => a.name.localeCompare(b.name),
      za: (a, b) => b.name.localeCompare(a.name),
      designation: (a, b) => (a.designation || "").localeCompare(b.designation || ""),
      workload: (a, b) => b.max_weekly_load - a.max_weekly_load,
    };
    filtered.sort(cmp[sortBy] || cmp.az);
    return filtered;
  }, [faculty, search, sortBy]);

  const groupedFaculty = useMemo(() => {
    const map = {};
    sortedFaculty.forEach((f) => {
      const key = f.department_name || "Unassigned";
      if (!map[key]) map[key] = [];
      map[key].push(f);
    });

    return Object.entries(map)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([dept, facs]) => ({ dept, facs }));
  }, [sortedFaculty]);

  const totalFiltered = groupedFaculty.reduce((s, g) => s + g.facs.length, 0);

  return (
    <DashboardLayout>
      <div className="page-head">
        <h1>Faculty Management</h1>
        <p>Register faculty with availability and subject eligibility.</p>
      </div>

      <BulkUploadCard
        title="Upload Faculty"
        endpoint="faculty/faculty/"
        requiredColumns={["name", "employee_id"]}
        templateFileName="faculty-upload-template.xlsx"
        templateSampleRow={{
          name: "Dr. John Doe", employee_id: "FAC1001",
          designation: "Professor", role: "REGULAR",
          max_lectures_per_day: 4, max_consecutive_lectures: 2,
          max_weekly_load: 18, is_active: true,
        }}
        mapRow={(row) => ({
          name: row.name,
          employee_id: row.employee_id,
          designation: row.designation || "",
          role: String(row.role || "REGULAR").toUpperCase(),
          max_lectures_per_day: toNumber(row.max_lectures_per_day,
            ROLE_DEFAULTS[String(row.role||"REGULAR").toUpperCase()]?.max_lectures_per_day ?? 4),
          max_consecutive_lectures: toNumber(row.max_consecutive_lectures,
            ROLE_DEFAULTS[String(row.role||"REGULAR").toUpperCase()]?.max_consecutive_lectures ?? 2),
          max_weekly_load: toNumber(row.max_weekly_load,
            ROLE_DEFAULTS[String(row.role||"REGULAR").toUpperCase()]?.max_weekly_load ?? 18),
          is_active: toBoolean(row.is_active, true),
        })}
        onUploadComplete={loadAll}
      />

      <div className="faculty-two-col">
        {/* ═══ LEFT: Form ═══ */}
        <section className="data-card faculty-form-card">
          <h3>
            <FaUserTie style={{ marginRight: 8, color: "var(--brand)" }} />
            {editId ? "Update Faculty Member" : "Register New Faculty"}
          </h3>

          {error   && <p className="upload-error">{error}</p>}
          {success && <p className="upload-success">{success}</p>}

          <form className="faculty-register-form" onSubmit={handleSubmit}>
            {/* Row 1: Name + Employee ID */}
            <div className="form-row-2">
              <div className="form-group">
                <label className="form-label">Full Name *</label>
                <input className="input" placeholder="e.g. Dr. John Doe" value={form.name}
                  onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))} required />
              </div>
              <div className="form-group">
                <label className="form-label">Employee ID *</label>
                <input className="input" placeholder="e.g. FAC1001" value={form.employee_id}
                  onChange={(e) => setForm((p) => ({ ...p, employee_id: e.target.value }))} required />
              </div>
            </div>

            {/* Row 2: Designation + Department */}
            <div className="form-row-2">
              <div className="form-group">
                <label className="form-label">Designation</label>
                <input className="input" placeholder="e.g. Professor, Assistant Professor"
                  value={form.designation}
                  onChange={(e) => setForm((p) => ({ ...p, designation: e.target.value }))} />
              </div>
              <div className="form-group">
                <label className="form-label">Department</label>
                <select className="input" value={form.department}
                  onChange={(e) => setForm((p) => ({ ...p, department: e.target.value }))}>
                  <option value="">— Select —</option>
                  {departments.map((d) => (
                    <option key={d.id} value={d.id}>{d.name}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Row 3: Role */}
            <div className="form-group">
              <label className="form-label">Role</label>
              <select className="input" value={form.role}
                onChange={(e) => handleRoleChange(e.target.value)}>
                {Object.entries(ROLE_LABELS).map(([k, v]) => (
                  <option key={k} value={k}>{v}</option>
                ))}
              </select>
              <span className="input-hint">
                Changing role auto-fills workload defaults below
              </span>
            </div>

            {/* Row 4: Workload — 3 fields in a row */}
            <div className="form-row-3">
              <div className="form-group">
                <label className="form-label">Max / Day</label>
                <select className="input" value={form.max_lectures_per_day}
                  onChange={(e) => setForm((p) => ({ ...p, max_lectures_per_day: e.target.value }))}>
                  {[1,2,3,4,5,6].map((n) => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Max Consec.</label>
                <select className="input" value={form.max_consecutive_lectures}
                  onChange={(e) => setForm((p) => ({ ...p, max_consecutive_lectures: e.target.value }))}>
                  {[1,2,3,4].map((n) => (
                    <option key={n} value={n}>{n}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Max / Week</label>
                <input className="input" type="number" min="1" max="30"
                  value={form.max_weekly_load}
                  onChange={(e) => setForm((p) => ({ ...p, max_weekly_load: e.target.value }))} />
              </div>
            </div>

            {/* ── Configure Availability ── */}
            <div className="form-group">
              <button type="button" className="avail-toggle-btn"
                onClick={() => setShowAvailability((v) => !v)}>
                <span>Configure Availability</span>
                {showAvailability ? <FaChevronUp /> : <FaChevronDown />}
              </button>
            </div>

            {showAvailability && (
              <div className="avail-config">
                {DAYS.map((d) => (
                  <div key={d.key} className="avail-day-row">
                    <div className="avail-day-header">
                      <span className="avail-day-label">{d.label}</span>
                      <label className="avail-allday-check">
                        <input type="checkbox" checked={availability[d.key].allDay}
                          onChange={() => toggleAllDay(d.key)} />
                        <span>All day</span>
                      </label>
                    </div>
                    <div className="avail-slots-row">
                      {SLOTS.map((s) => (
                        <label key={s}
                          className={`avail-slot-chip ${availability[d.key].slots[s] ? "active" : ""}`}
                          title={SLOT_TIMES[s]}>
                          <input type="checkbox" checked={availability[d.key].slots[s]}
                            onChange={() => toggleSlot(d.key, s)} />
                          Slot {s}
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* ── Configure Eligibility ── */}
            <div className="form-group">
              <button type="button" className="avail-toggle-btn"
                onClick={() => setShowEligibility((v) => !v)}>
                <span>Configure Eligibility</span>
                {showEligibility ? <FaChevronUp /> : <FaChevronDown />}
              </button>
              <span className="input-hint">
                Click courses to EXCLUDE them — unconfigured = can teach everything
              </span>
            </div>

            {showEligibility && (
              <EligibilityConfigurator
                programs={programs}
                courses={courses}
                excludedSubjects={excludedSubjects}
                toggleExclusion={toggleExclusion}
                excludedPrograms={excludedPrograms}
                toggleProgExcl={toggleProgExcl}
                excludedSemesters={excludedSemesters}
                toggleSemExcl={toggleSemExcl}
              />
            )}

            {/* ── Submit ── */}
            <div className="form-group form-group-btn" style={{ display: "flex", gap: 10 }}>
              <button type="submit" className="btn btn-primary" disabled={submitting}
                style={{ flex: 1, justifyContent: "center" }}>
                <FaUserTie style={{ marginRight: 8 }} />
                {submitting ? "Saving…" : editId ? "Update Faculty" : "Register Faculty"}
              </button>
              {editId && (
                <button type="button" className="btn btn-secondary" onClick={cancelEdit}>
                  <FaTimes />
                </button>
              )}
            </div>
          </form>
        </section>

        {/* ═══ RIGHT: Faculty List or Detail View ═══ */}
        <section className="data-card faculty-list-card" style={{ padding: 0, overflow: "hidden" }}>
          {viewingFaculty ? (
            <FacultyDetailView
              fac={viewingFaculty}
              programs={programs}
              courses={courses}
              exclusions={eligibilityData}
              progExclusions={progExclData}
              semExclusions={semExclData}
              availabilities={availabilityData}
              onBack={() => setViewingFaculty(null)}
            />
          ) : (
            <>
              {/* Header */}
              <div className="prog-list-header">
                <div>
                  <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "var(--text)" }}>
                    Faculty
                  </h3>
                  <p style={{ margin: "2px 0 0", fontSize: 12, color: "var(--muted)" }}>
                    {faculty.length} members across {
                      Object.keys(faculty.reduce((m, f) => { m[f.department_name || "Other"] = 1; return m; }, {})).length
                    } departments
                  </p>
                </div>
                <div style={{ display: "flex", gap: 6, alignItems: "center" }}>
                  {/* Sort dropdown */}
                  <div className="fac-sort-wrap">
                    <FaSortAmountDown className="fac-sort-icon" />
                    <select className="fac-sort-select" value={sortBy}
                      onChange={(e) => setSortBy(e.target.value)}>
                      <option value="az">Name A → Z</option>
                      <option value="za">Name Z → A</option>
                      <option value="designation">Designation</option>
                      <option value="workload">Workload (high → low)</option>
                    </select>
                  </div>
                  {/* Search */}
                  <div className="pdc-search-wrap">
                    <FaSearch className="pdc-search-icon" />
                    <input className="input pdc-search-input" placeholder="Search…"
                      value={search} onChange={(e) => setSearch(e.target.value)} />
                  </div>
                </div>
              </div>

              {/* Body */}
              <div className="dept-list-body">
                {loading ? (
                  <p className="upload-help" style={{ padding: "20px" }}>Loading…</p>
                ) : totalFiltered === 0 ? (
                  <p className="upload-help" style={{ padding: "20px" }}>
                    {search ? "No faculty match your search." : "No faculty yet."}
                  </p>
                ) : (
                  groupedFaculty.map(({ dept, facs }) => (
                    <div key={dept} className="dept-section">
                      <div className="dept-section-header">
                        <FaUserTie className="dept-section-icon" />
                        <span className="dept-section-name">{dept}</span>
                        <span className="dept-section-count">{facs.length} members</span>
                      </div>
                      <div className="fac-card-grid">
                        {facs.map((f) => (
                          <FacultyCard key={f.id} fac={f}
                            onEdit={handleEdit}
                            onDelete={handleDelete}
                            onClick={() => setViewingFaculty(f)}
                          />
                        ))}
                      </div>
                    </div>
                  ))
                )}
              </div>
            </>
          )}
        </section>
      </div>
    </DashboardLayout>
  );
}

export default FacultyPage;
