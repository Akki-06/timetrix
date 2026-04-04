import { useCallback, useEffect, useState, useMemo } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import BulkUploadCard from "../components/BulkUploadCard";
import { toNumber } from "../utils/spreadsheet";
import { asList, extractError } from "../utils/helpers";
import { FaUsers, FaTrash, FaBook, FaMagic, FaChevronDown, FaChevronRight, FaEdit, FaTimes } from "react-icons/fa";

const DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT"];

const INITIAL_FORM = {
  program: "",
  semester: "",
  section: "",
  strength: 45,
  description: "",
  working_days: ["MON", "TUE", "WED", "THU", "FRI"],
};

function SectionsPage() {
  const [groups, setGroups]       = useState([]);
  const [programs, setPrograms]   = useState([]);
  const [loading, setLoading]     = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]         = useState("");
  const [success, setSuccess]     = useState("");
  const [form, setForm]           = useState(INITIAL_FORM);
  const [editId, setEditId]       = useState(null);

  /* ── Course Offerings panel state ── */
  const [expandedGroup, setExpandedGroup] = useState(null);
  const [offerings, setOfferings]         = useState([]);
  const [offeringsLoading, setOfferingsLoading] = useState(false);
  const [autoAssigning, setAutoAssigning] = useState(false);

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

  useEffect(() => { loadAll(); }, [loadAll]);

  // Semester options dynamically based on selected program's total_semesters
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
        program:     Number(form.program),
        semester:    Number(form.semester),
        section:     form.section.trim().toUpperCase(),
        strength:    Number(form.strength),
        description: form.description.trim(),
        working_days: form.working_days,
      };

      if (editId) {
        // quick-create handles updating if it exists
        await api.post("academics/student-groups/quick-create/", payload);
        setSuccess("Section updated successfully.");
        setEditId(null);
      } else {
        await api.post("academics/student-groups/quick-create/", payload);
        setSuccess("Section registered successfully.");
      }

      setForm(INITIAL_FORM);
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
    if (!window.confirm("Delete this section? Associated course offerings and allocations will also be removed.")) return;
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

  /* ── Course Offerings helpers ── */
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

  // Group table rows by program for cleaner display
  const grouped = useMemo(() => {
    const map = {};
    for (const g of groups) {
      const key = `${g.program_code}`;
      if (!map[key]) map[key] = { program_name: g.program_name, program_code: g.program_code, rows: [] };
      map[key].rows.push(g);
    }
    // Sort rows within each group by semester then section name
    for (const key of Object.keys(map)) {
      map[key].rows.sort((a, b) =>
        a.semester !== b.semester ? a.semester - b.semester : a.name.localeCompare(b.name)
      );
    }
    return Object.values(map).sort((a, b) => a.program_code.localeCompare(b.program_code));
  }, [groups]);

  return (
    <DashboardLayout>
      <div className="page-head">
        <h1>Section Management</h1>
        <p>
          Register student sections per program and semester. The scheduler
          uses this to know how many parallel sections to timetable and
          which room sizes to target.
        </p>
      </div>

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
            program:     prog?.id || null,
            semester:    toNumber(row.semester, 1),
            section:     String(row.section || "").trim().toUpperCase(),
            strength:    toNumber(row.strength, 45),
            description: String(row.description || "").trim(),
          };
        }}
        onUploadComplete={loadAll}
      />

      <div className="faculty-two-col">
        {/* ── LEFT: Register Section Form ── */}
        <section className="data-card faculty-form-card">
          <h3>
            <FaUsers style={{ marginRight: 8, color: "var(--brand)" }} />
            {editId ? "Update Section" : "Register Section"}
          </h3>

          {error   && <p className="upload-error">{error}</p>}
          {success && <p className="upload-success">{success}</p>}

          <form className="faculty-register-form" onSubmit={handleSubmit}>
            {/* Program */}
            <div className="form-group">
              <label className="form-label">Program *</label>
              <select
                className="input"
                value={form.program}
                onChange={(e) =>
                  setForm((p) => ({ ...p, program: e.target.value, semester: "" }))
                }
                required
              >
                <option value="">Choose program</option>
                {programs.map((p) => (
                  <option key={p.id} value={p.id}>
                    {p.display_name || p.name} ({p.code})
                  </option>
                ))}
              </select>
            </div>

            {/* Semester — dynamic based on program */}
            <div className="form-group">
              <label className="form-label">Semester *</label>
              <select
                className="input"
                value={form.semester}
                onChange={(e) =>
                  setForm((p) => ({ ...p, semester: e.target.value }))
                }
                disabled={!form.program}
                required
              >
                <option value="">
                  {form.program ? "Choose semester" : "Select program first"}
                </option>
                {semesterOptions.map((s) => (
                  <option key={s} value={s}>Semester {s}</option>
                ))}
              </select>
            </div>

            {/* Section letter */}
            <div className="form-group">
              <label className="form-label">Section *</label>
              <input
                className="input"
                placeholder="e.g. A, B, C or 1, 2"
                value={form.section}
                onChange={(e) =>
                  setForm((p) => ({ ...p, section: e.target.value }))
                }
                maxLength={10}
                required
              />
              <span className="input-hint">
                Section identifier — A, B, C for parallel batches
              </span>
            </div>

            {/* Strength */}
            <div className="form-group">
              <label className="form-label">Student Strength *</label>
              <input
                className="input"
                type="number"
                min="1"
                max="300"
                value={form.strength}
                onChange={(e) =>
                  setForm((p) => ({ ...p, strength: e.target.value }))
                }
                required
              />
              <span className="input-hint">
                Scheduler uses this to match rooms with sufficient capacity
              </span>
            </div>

            {/* Description (optional) */}
            <div className="form-group">
              <label className="form-label">Note (optional)</label>
              <input
                className="input"
                placeholder="e.g. Honours batch, Evening shift"
                value={form.description}
                onChange={(e) =>
                  setForm((p) => ({ ...p, description: e.target.value }))
                }
              />
            </div>

            {/* Working Days */}
            <div className="form-group" style={{ marginBottom: "1rem" }}>
              <label className="form-label">Working Days *</label>
              <div className="custom-checkbox-group">
                {DAYS.map(day => (
                  <label key={day} className="custom-checkbox-label">
                    <input
                      type="checkbox"
                      className="custom-checkbox"
                      checked={form.working_days.includes(day)}
                      onChange={(e) => {
                        if (e.target.checked) {
                          setForm(p => ({ ...p, working_days: [...p.working_days, day] }));
                        } else {
                          setForm(p => ({ ...p, working_days: p.working_days.filter(d => d !== day) }));
                        }
                      }}
                    />
                    <span className="checkbox-text">{day}</span>
                  </label>
                ))}
              </div>
              <span className="input-hint">Uncheck days to declare them as holidays for this section.</span>
            </div>

            <div className="form-group form-group-btn" style={{ display: "flex", gap: "10px" }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={submitting}
                style={{ flex: 1, justifyContent: "center" }}
              >
                <FaUsers style={{ marginRight: 8 }} />
                {submitting ? "Saving..." : editId ? "Update Section" : "Register Section"}
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

        {/* ── RIGHT: Existing Sections ── */}
        <section className="data-card faculty-list-card">
          <h3>Registered Sections ({groups.length})</h3>
          {loading ? (
            <p className="upload-help">Loading sections...</p>
          ) : groups.length === 0 ? (
            <p className="upload-help" style={{ padding: 24, textAlign: "center", color: "var(--muted)" }}>
              No sections registered yet. Add one using the form.
            </p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Program</th>
                    <th>Semester</th>
                    <th>Year</th>
                    <th>Section</th>
                    <th>Strength</th>
                    <th>Note</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {grouped.map((grp) =>
                    grp.rows.map((g, idx) => (
                      <tr key={g.id} style={{ cursor: "pointer" }} onClick={() => toggleExpand(g.id)}>
                        {idx === 0 && (
                          <td rowSpan={grp.rows.length} style={{ fontWeight: 600 }}>
                            <div className="fac-name-cell">
                              <FaUsers style={{ color: "var(--brand)", flexShrink: 0 }} />
                              <span>{grp.program_name}</span>
                            </div>
                          </td>
                        )}
                        <td>
                          <span className="course-sem-badge">Sem {g.semester}</span>
                        </td>
                        <td style={{ color: "var(--muted)" }}>Year {g.year}</td>
                        <td>
                          <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
                            {expandedGroup === g.id ? <FaChevronDown size={10} /> : <FaChevronRight size={10} />}
                            <strong>{g.name}</strong>
                          </div>
                        </td>
                        <td>{g.strength}</td>
                        <td style={{ color: "var(--muted)", fontSize: "0.85em" }}>
                          {g.description || "\u2014"}
                        </td>
                        <td>
                          <div className="table-actions">
                            <button
                              className="action-btn"
                              title="Edit Section"
                              onClick={(e) => { e.stopPropagation(); handleEdit(g); }}
                            >
                              <FaEdit style={{ color: "#3b82f6" }} />
                            </button>
                            <button
                              className="action-btn danger"
                              title="Delete"
                              onClick={(e) => { e.stopPropagation(); handleDelete(g.id); }}
                            >
                              <FaTrash />
                            </button>
                          </div>
                        </td>
                      </tr>
                    ))
                  )}
                </tbody>
              </table>
            </div>
          )}

          {/* ── Expanded Course Offerings Panel ── */}
          {expandedGroup && (
            <div className="data-card" style={{ marginTop: 12, background: "var(--bg-card)" }}>
              <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", flexWrap: "wrap", gap: 8, marginBottom: 12 }}>
                <h4 style={{ margin: 0, display: "flex", alignItems: "center", gap: 8 }}>
                  <FaBook style={{ color: "var(--brand)" }} />
                  Course Offerings for Section {groups.find((g) => g.id === expandedGroup)?.name || ""}
                </h4>
                <button
                  className="btn-primary btn-with-icon"
                  style={{ fontSize: "0.85em" }}
                  disabled={autoAssigning}
                  onClick={() => handleAutoAssign(expandedGroup)}
                >
                  <FaMagic />
                  {autoAssigning ? "Assigning..." : "Auto-Assign Courses"}
                </button>
              </div>

              {offeringsLoading ? (
                <p className="upload-help">Loading offerings...</p>
              ) : offerings.length === 0 ? (
                <p style={{ color: "var(--muted)", textAlign: "center", padding: 16 }}>
                  No course offerings yet. Click "Auto-Assign Courses" to populate from the program syllabus.
                </p>
              ) : (
                <div className="table-wrap">
                  <table>
                    <thead>
                      <tr>
                        <th>Course Code</th>
                        <th>Course Name</th>
                        <th>Type</th>
                        <th>Weekly Load</th>
                        <th>Faculty</th>
                        <th style={{ width: 40 }}></th>
                      </tr>
                    </thead>
                    <tbody>
                      {offerings.map((o) => (
                        <tr key={o.id}>
                          <td><strong>{o.course_code || o.course}</strong></td>
                          <td>{o.course_name || "\u2014"}</td>
                          <td>
                            <span className="course-sem-badge">{o.course_type || "\u2014"}</span>
                          </td>
                          <td>{o.weekly_load}</td>
                          <td style={{ color: o.faculty_name ? "inherit" : "var(--muted)" }}>
                            {o.faculty_name || "Unassigned"}
                          </td>
                          <td>
                            <button
                              className="icon-btn danger"
                              title="Remove offering"
                              onClick={() => handleDeleteOffering(o.id)}
                            >
                              <FaTrash size={12} />
                            </button>
                          </td>
                        </tr>
                      ))}
                    </tbody>
                  </table>
                </div>
              )}
            </div>
          )}
        </section>
      </div>
    </DashboardLayout>
  );
}

export default SectionsPage;
