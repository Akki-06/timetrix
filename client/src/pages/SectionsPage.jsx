import { useCallback, useEffect, useState, useMemo } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import BulkUploadCard from "../components/BulkUploadCard";
import { toNumber } from "../utils/spreadsheet";
import { asList, extractError, courseDisplayCode } from "../utils/helpers";
import {
  FaUsers, FaTrash, FaBook, FaMagic, FaChevronDown, FaChevronRight,
  FaEdit, FaTimes, FaPlus, FaGraduationCap, FaLayerGroup, FaUserGraduate,
} from "react-icons/fa";

const DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT"];
const DAY_SHORT = { MON: "M", TUE: "T", WED: "W", THU: "Th", FRI: "F", SAT: "S" };

const INITIAL_FORM = {
  program: "",
  semester: "",
  section: "",
  strength: 45,
  description: "",
  working_days: ["MON", "TUE", "WED", "THU", "FRI"],
};

function SectionsPage() {
  const [groups, setGroups] = useState([]);
  const [programs, setPrograms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [form, setForm] = useState(INITIAL_FORM);
  const [editId, setEditId] = useState(null);
  const [showForm, setShowForm] = useState(false);

  /* Course Offerings panel state */
  const [expandedGroup, setExpandedGroup] = useState(null);
  const [offerings, setOfferings] = useState([]);
  const [offeringsLoading, setOfferingsLoading] = useState(false);
  const [autoAssigning, setAutoAssigning] = useState(false);

  /* Expanded programs/years */
  const [expandedProgs, setExpandedProgs] = useState({});
  const [expandedYears, setExpandedYears] = useState({});

  const loadAll = useCallback(async () => {
    try {
      setLoading(true);
      const [groupResp, progResp] = await Promise.all([
        api.get("academics/student-groups/").catch(() => null),
        api.get("academics/programs/").catch(() => null),
      ]);
      setGroups(groupResp ? asList(groupResp.data) : []);
      setPrograms(progResp ? asList(progResp.data) : []);
    } catch (err) {
      console.error("Failed to load:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const semesterOptions = useMemo(() => {
    const prog = programs.find((p) => String(p.id) === String(form.program));
    const max = prog?.total_semesters || 8;
    return Array.from({ length: max }, (_, i) => i + 1);
  }, [form.program, programs]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSubmitting(true);
    try {
      const payload = {
        program: Number(form.program),
        semester: Number(form.semester),
        section: form.section.trim().toUpperCase(),
        strength: Number(form.strength),
        description: form.description.trim(),
        working_days: form.working_days,
      };
      await api.post("academics/student-groups/quick-create/", payload);
      setSuccess(editId ? "Section updated successfully." : "Section registered successfully.");
      setEditId(null);
      setForm(INITIAL_FORM);
      setShowForm(false);
      loadAll();
    } catch (err) {
      setError(extractError(err, editId ? "Failed to update section." : "Failed to register section."));
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (group) => {
    setEditId(group.id);
    setForm({
      program: group.program_id || "",
      semester: group.semester || "",
      section: group.name,
      strength: group.strength,
      description: group.description || "",
      working_days: group.working_days && group.working_days.length > 0 ? group.working_days : ["MON", "TUE", "WED", "THU", "FRI"],
    });
    setShowForm(true);
    setError("");
    setSuccess("");
  };

  const cancelEdit = () => {
    setEditId(null);
    setForm(INITIAL_FORM);
    setShowForm(false);
    setError("");
    setSuccess("");
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this section? Associated course offerings will also be removed.")) return;
    try {
      await api.delete(`academics/student-groups/${id}/`);
      if (expandedGroup === id) {
        setExpandedGroup(null);
        setOfferings([]);
      }
      loadAll();
    } catch (err) {
      setError(extractError(err, "Failed to delete section."));
    }
  };

  /* Course Offerings helpers */
  const loadOfferings = useCallback(async (groupId) => {
    try {
      setOfferingsLoading(true);
      const resp = await api.get(`academics/course-offerings/?student_group=${groupId}`);
      setOfferings(asList(resp.data));
    } catch {
      setOfferings([]);
    } finally {
      setOfferingsLoading(false);
    }
  }, []);

  const toggleExpand = (groupId) => {
    if (expandedGroup === groupId) {
      setExpandedGroup(null);
      setOfferings([]);
    } else {
      setExpandedGroup(groupId);
      loadOfferings(groupId);
    }
  };

  const handleAutoAssign = async (groupId) => {
    try {
      setAutoAssigning(true);
      const resp = await api.post(`academics/student-groups/${groupId}/auto-assign-courses/`);
      const { created, already_existed } = resp.data;
      setSuccess(`Auto-assigned: ${created} new, ${already_existed} already existed.`);
      loadOfferings(groupId);
    } catch (err) {
      setError(extractError(err, "Auto-assign failed."));
    } finally {
      setAutoAssigning(false);
    }
  };

  const handleDeleteOffering = async (offeringId) => {
    try {
      await api.delete(`academics/course-offerings/${offeringId}/`);
      setOfferings((prev) => prev.filter((o) => o.id !== offeringId));
    } catch (err) {
      setError(extractError(err, "Failed to remove offering."));
    }
  };

  /* ── Build hierarchy: Program → Year → Sections ── */
  const hierarchy = useMemo(() => {
    const map = {};
    for (const g of groups) {
      const progKey = g.program_code || "Unknown";
      if (!map[progKey]) {
        map[progKey] = {
          program_name: g.program_name,
          program_code: g.program_code,
          totalStudents: 0,
          totalSections: 0,
          years: {},
        };
      }
      const year = g.year || Math.ceil(g.semester / 2);
      if (!map[progKey].years[year]) {
        map[progKey].years[year] = { sections: [], semesters: new Set() };
      }
      map[progKey].years[year].sections.push(g);
      map[progKey].years[year].semesters.add(g.semester);
      map[progKey].totalStudents += g.strength || 0;
      map[progKey].totalSections++;
    }
    // Sort sections within each year
    for (const prog of Object.values(map)) {
      for (const year of Object.values(prog.years)) {
        year.sections.sort((a, b) =>
          a.semester !== b.semester ? a.semester - b.semester : a.name.localeCompare(b.name)
        );
      }
    }
    return Object.values(map).sort((a, b) => a.program_code.localeCompare(b.program_code));
  }, [groups]);

  const toggleProg = (code) => setExpandedProgs((p) => ({ ...p, [code]: !p[code] }));
  const toggleYear = (key) => setExpandedYears((p) => ({ ...p, [key]: !p[key] }));

  // auto-expand all on load
  useEffect(() => {
    if (hierarchy.length > 0 && Object.keys(expandedProgs).length === 0) {
      const ep = {};
      const ey = {};
      hierarchy.forEach((p) => {
        ep[p.program_code] = true;
        Object.keys(p.years).forEach((y) => {
          ey[`${p.program_code}-${y}`] = true;
        });
      });
      setExpandedProgs(ep);
      setExpandedYears(ey);
    }
  }, [hierarchy]);

  return (
    <DashboardLayout>
      {/* ── Header ── */}
      <div className="sec-page-header">
        <div>
          <h1 className="sec-page-title">Sections</h1>
          <p className="sec-page-sub">
            Manage student sections per program and semester. Groups are used by the scheduler
            to assign rooms by capacity.
          </p>
        </div>
        <button className="sec-add-btn" onClick={() => { setShowForm(!showForm); setEditId(null); setForm(INITIAL_FORM); }}>
          {showForm ? <><FaTimes /> Close</> : <><FaPlus /> Add Section</>}
        </button>
      </div>

      {/* Alerts */}
      {error && <div className="sec-alert sec-alert-error">{error}</div>}
      {success && <div className="sec-alert sec-alert-success">{success}</div>}

      {/* ── Inline Add/Edit Form ── */}
      {showForm && (
        <div className="sec-form-panel">
          <div className="sec-form-header">
            <h3>{editId ? "Update Section" : "Register New Section"}</h3>
          </div>
          <form className="sec-form-grid" onSubmit={handleSubmit}>
            <div className="sec-field">
              <label>Program <span className="sec-req">*</span></label>
              <select
                value={form.program}
                onChange={(e) => setForm((p) => ({ ...p, program: e.target.value, semester: "" }))}
                required
              >
                <option value="">Choose program</option>
                {[...programs].sort((a, b) => (a.display_name || a.name || "").localeCompare(b.display_name || b.name || "")).map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.display_name || p.name} ({p.code})
                  </option>
                ))}
              </select>
            </div>

            <div className="sec-field">
              <label>Semester <span className="sec-req">*</span></label>
              <select
                value={form.semester}
                onChange={(e) => setForm((p) => ({ ...p, semester: e.target.value }))}
                disabled={!form.program}
                required
              >
                <option value="">{form.program ? "Choose semester" : "Select program first"}</option>
                {semesterOptions.map((s) => (
                  <option key={s} value={s}>Semester {s}</option>
                ))}
              </select>
            </div>

            <div className="sec-field">
              <label>Section <span className="sec-req">*</span></label>
              <input
                placeholder="e.g. A, B, C"
                value={form.section}
                onChange={(e) => setForm((p) => ({ ...p, section: e.target.value }))}
                maxLength={10}
                required
              />
            </div>

            <div className="sec-field">
              <label>Student Strength <span className="sec-req">*</span></label>
              <input
                type="number"
                min="1"
                max="300"
                value={form.strength}
                onChange={(e) => setForm((p) => ({ ...p, strength: e.target.value }))}
                required
              />
            </div>

            <div className="sec-field sec-field-wide">
              <label>Note <span className="sec-opt">(optional)</span></label>
              <input
                placeholder="e.g. Honours batch, Evening shift"
                value={form.description}
                onChange={(e) => setForm((p) => ({ ...p, description: e.target.value }))}
              />
            </div>

            <div className="sec-field sec-field-wide">
              <label>Working Days <span className="sec-req">*</span></label>
              <div className="sec-days-row">
                {DAYS.map((day) => (
                  <label
                    key={day}
                    className={`sec-day-chip ${form.working_days.includes(day) ? "active" : ""}`}
                  >
                    <input
                      type="checkbox"
                      checked={form.working_days.includes(day)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setForm((p) => ({ ...p, working_days: [...p.working_days, day] }));
                        } else {
                          setForm((p) => ({ ...p, working_days: p.working_days.filter((d) => d !== day) }));
                        }
                      }}
                    />
                    {DAY_SHORT[day]}
                  </label>
                ))}
              </div>
            </div>

            <div className="sec-form-actions">
              <button type="submit" className="sec-submit-btn" disabled={submitting}>
                {submitting ? "Saving..." : editId ? "Update Section" : "Register Section"}
              </button>
              {editId && (
                <button type="button" className="sec-cancel-btn" onClick={cancelEdit}>
                  Cancel
                </button>
              )}
            </div>
          </form>
        </div>
      )}

      {/* ── Bulk Upload ── */}
      <BulkUploadCard
        title="Upload Sections"
        endpoint="academics/student-groups/quick-create/"
        requiredColumns={["program_code", "semester", "section", "strength"]}
        templateFileName="sections-upload-template.xlsx"
        templateSampleRow={{
          program_code: "BCA",
          semester: 5,
          section: "A",
          strength: 45,
          description: "",
        }}
        mapRow={(row) => {
          const progCode = String(row.program_code || "").trim();
          const prog = programs.find(
            (p) => p.code.toLowerCase() === progCode.toLowerCase()
          );
          return {
            program: prog?.id || null,
            semester: toNumber(row.semester, 1),
            section: String(row.section || "").trim().toUpperCase(),
            strength: toNumber(row.strength, 45),
            description: String(row.description || "").trim(),
          };
        }}
        onUploadComplete={loadAll}
      />

      {/* ── Section Hierarchy ── */}
      {loading ? (
        <div className="sec-loading">
          <div className="sec-loading-spinner" />
          Loading sections...
        </div>
      ) : groups.length === 0 ? (
        <div className="sec-empty">
          <FaUsers className="sec-empty-icon" />
          <h3>No sections registered yet</h3>
          <p>Click "Add Section" to register your first student section.</p>
        </div>
      ) : (
        <div className="sec-hierarchy">
          {/* Summary strip */}
          <div className="sec-summary-strip">
            <div className="sec-summary-item">
              <FaGraduationCap />
              <span><strong>{hierarchy.length}</strong> Programs</span>
            </div>
            <div className="sec-summary-item">
              <FaLayerGroup />
              <span><strong>{groups.length}</strong> Sections</span>
            </div>
            <div className="sec-summary-item">
              <FaUserGraduate />
              <span><strong>{groups.reduce((s, g) => s + (g.strength || 0), 0)}</strong> Students</span>
            </div>
          </div>

          {/* Program accordion */}
          {hierarchy.map((prog) => (
            <div key={prog.program_code} className="sec-program-block">
              {/* Program header */}
              <button className="sec-program-header" onClick={() => toggleProg(prog.program_code)}>
                <div className="sec-program-left">
                  {expandedProgs[prog.program_code] ? <FaChevronDown size={12} /> : <FaChevronRight size={12} />}
                  <div className="sec-program-icon">
                    <FaGraduationCap />
                  </div>
                  <div>
                    <span className="sec-program-name">{prog.program_name}</span>
                    <span className="sec-program-code">{prog.program_code}</span>
                  </div>
                </div>
                <div className="sec-program-meta">
                  <span className="sec-meta-badge">{prog.totalSections} sections</span>
                  <span className="sec-meta-badge">{prog.totalStudents} students</span>
                </div>
              </button>

              {/* Expanded years */}
              {expandedProgs[prog.program_code] && (
                <div className="sec-years-container">
                  {Object.entries(prog.years)
                    .sort(([a], [b]) => Number(a) - Number(b))
                    .map(([year, data]) => {
                      const yearKey = `${prog.program_code}-${year}`;
                      return (
                        <div key={yearKey} className="sec-year-block">
                          <button className="sec-year-header" onClick={() => toggleYear(yearKey)}>
                            {expandedYears[yearKey] ? <FaChevronDown size={10} /> : <FaChevronRight size={10} />}
                            <span className="sec-year-label">Year {year}</span>
                            <span className="sec-year-sems">
                              Sem {[...data.semesters].sort((a, b) => a - b).join(", ")}
                            </span>
                            <span className="sec-year-count">{data.sections.length} sections</span>
                          </button>

                          {expandedYears[yearKey] && (
                            <div className="sec-cards-grid">
                              {data.sections.map((g) => (
                                <div
                                  key={g.id}
                                  className={`sec-card ${expandedGroup === g.id ? "sec-card-active" : ""}`}
                                >
                                  <div className="sec-card-top">
                                    <div className="sec-card-name-row">
                                      <span className="sec-card-name">{g.name}</span>
                                      <span className="sec-card-sem-badge">Sem {g.semester}</span>
                                    </div>
                                    <div className="sec-card-actions">
                                      <button className="sec-icon-btn" title="Edit" onClick={() => handleEdit(g)}>
                                        <FaEdit />
                                      </button>
                                      <button className="sec-icon-btn sec-icon-danger" title="Delete" onClick={() => handleDelete(g.id)}>
                                        <FaTrash />
                                      </button>
                                    </div>
                                  </div>

                                  <div className="sec-card-details">
                                    <div className="sec-detail-row">
                                      <span className="sec-detail-label">Strength</span>
                                      <span className="sec-detail-value">{g.strength} students</span>
                                    </div>
                                    {g.description && (
                                      <div className="sec-detail-row">
                                        <span className="sec-detail-label">Note</span>
                                        <span className="sec-detail-value">{g.description}</span>
                                      </div>
                                    )}
                                    <div className="sec-detail-row">
                                      <span className="sec-detail-label">Working Days</span>
                                      <div className="sec-detail-days">
                                        {DAYS.map((d) => (
                                          <span
                                            key={d}
                                            className={`sec-day-mini ${(g.working_days || ["MON", "TUE", "WED", "THU", "FRI"]).includes(d) ? "on" : "off"}`}
                                          >
                                            {DAY_SHORT[d]}
                                          </span>
                                        ))}
                                      </div>
                                    </div>
                                  </div>

                                  <button
                                    className="sec-card-expand-btn"
                                    onClick={() => toggleExpand(g.id)}
                                  >
                                    <FaBook />
                                    {expandedGroup === g.id ? "Hide Courses" : "View Courses"}
                                    {expandedGroup === g.id ? <FaChevronDown size={10} /> : <FaChevronRight size={10} />}
                                  </button>

                                  {/* Course offerings inline */}
                                  {expandedGroup === g.id && (
                                    <div className="sec-offerings-panel">
                                      <div className="sec-offerings-header">
                                        <span>Course Offerings</span>
                                        <button
                                          className="sec-auto-btn"
                                          disabled={autoAssigning}
                                          onClick={() => handleAutoAssign(g.id)}
                                        >
                                          <FaMagic />
                                          {autoAssigning ? "Assigning..." : "Auto-Assign"}
                                        </button>
                                      </div>

                                      {offeringsLoading ? (
                                        <p className="sec-offerings-empty">Loading...</p>
                                      ) : offerings.length === 0 ? (
                                        <p className="sec-offerings-empty">
                                          No offerings yet. Click Auto-Assign to populate.
                                        </p>
                                      ) : (
                                        <div className="sec-offerings-list">
                                          {offerings.map((o) => (
                                            <div key={o.id} className="sec-offering-row">
                                              <div className="sec-offering-info">
                                                <strong>{courseDisplayCode(o.course_code || o.course)}</strong>
                                                <span>{o.course_name || "—"}</span>
                                              </div>
                                              <span className="sec-offering-type">{o.course_type || "—"}</span>
                                              <span className={`sec-offering-fac ${o.faculty_name ? "" : "unassigned"}`}>
                                                {o.faculty_name || "Unassigned"}
                                              </span>
                                              <button className="sec-icon-btn sec-icon-danger" onClick={() => handleDeleteOffering(o.id)}>
                                                <FaTrash size={11} />
                                              </button>
                                            </div>
                                          ))}
                                        </div>
                                      )}
                                    </div>
                                  )}
                                </div>
                              ))}
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

export default SectionsPage;
