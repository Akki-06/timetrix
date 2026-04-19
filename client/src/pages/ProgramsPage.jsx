import { useCallback, useEffect, useState, useMemo } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import BulkUploadCard from "../components/BulkUploadCard";
import { asList, extractError } from "../utils/helpers";
import {
  FaUniversity, FaTrash, FaEdit, FaTimes,
  FaGraduationCap, FaLayerGroup, FaCalendarAlt, FaSearch,
} from "react-icons/fa";

const INITIAL_FORM = {
  department: "",
  name: "",
  code: "",
  specialization: "",
  total_years: 4,
  total_semesters: 8,
};

/* ══════════════════════════════════════════════════════════════════════════
   Single Program Card — displayed inside a department group grid
   ══════════════════════════════════════════════════════════════════════════ */
function ProgramCard({ prog, onEdit, onDelete }) {
  return (
    <div className="prog-detail-card">
      {/* Top row: code badge + duration */}
      <div className="pdc-top">
        <code className="pdc-code">{prog.code}</code>
        <span className="pdc-duration">
          <FaCalendarAlt style={{ fontSize: 9, marginRight: 4 }} />
          {prog.total_years} yrs
        </span>
      </div>

      {/* Program display name */}
      <div className="pdc-name">{prog.display_name || prog.name}</div>

      {/* Meta: semesters */}
      <div className="pdc-meta">
        <span className="pdc-sems">
          <FaLayerGroup style={{ fontSize: 10, marginRight: 4 }} />
          {prog.total_semesters} semesters
        </span>
      </div>

      {/* Actions */}
      <div className="pdc-actions">
        <button
          className="action-btn"
          onClick={() => onEdit(prog)}
          title="Edit program"
        >
          <FaEdit style={{ color: "#3b82f6" }} />
        </button>
        <button
          className="action-btn danger"
          onClick={() => onDelete(prog.id)}
          title="Delete program"
        >
          <FaTrash />
        </button>
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
   Department Section — header + grid of program cards
   ══════════════════════════════════════════════════════════════════════════ */
function DeptSection({ deptName, programs, onEdit, onDelete }) {
  return (
    <div className="dept-section">
      <div className="dept-section-header">
        <FaUniversity className="dept-section-icon" />
        <span className="dept-section-name">{deptName}</span>
        <span className="dept-section-count">{programs.length} programs</span>
      </div>
      <div className="pdc-grid">
        {programs.map((p) => (
          <ProgramCard
            key={p.id}
            prog={p}
            onEdit={onEdit}
            onDelete={onDelete}
          />
        ))}
      </div>
    </div>
  );
}

/* ══════════════════════════════════════════════════════════════════════════
   Main Page
   ══════════════════════════════════════════════════════════════════════════ */
function ProgramsPage() {
  const [programs, setPrograms]     = useState([]);
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading]       = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]           = useState("");
  const [success, setSuccess]       = useState("");
  const [form, setForm]             = useState(INITIAL_FORM);
  const [editId, setEditId]         = useState(null);
  const [search, setSearch]         = useState("");

  const loadAll = useCallback(async () => {
    try {
      setLoading(true);
      const [progResp, deptResp] = await Promise.all([
        api.get("academics/programs/").catch(() => null),
        api.get("academics/departments/").catch(() => null),
      ]);
      setPrograms(progResp ? asList(progResp.data) : []);
      setDepartments(deptResp ? asList(deptResp.data) : []);
    } catch (err) {
      console.error("Failed to load data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  /* ── Submit ──────────────────────────────────── */
  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(""); setSuccess(""); setSubmitting(true);
    try {
      const payload = {
        name:             form.name.trim(),
        code:             form.code.trim(),
        department:       Number(form.department),
        specialization:   form.specialization.trim(),
        total_years:      Number(form.total_years),
        total_semesters:  Number(form.total_semesters),
      };
      if (editId) {
        await api.patch(`academics/programs/${editId}/`, payload);
        setSuccess("Program updated successfully.");
        setEditId(null);
      } else {
        await api.post("academics/programs/", payload);
        setSuccess("Program created successfully.");
      }
      setForm(INITIAL_FORM);
      loadAll();
    } catch (err) {
      setError(extractError(err, editId ? "Failed to update program." : "Failed to create program."));
    } finally {
      setSubmitting(false);
    }
  };

  const handleEdit = (prog) => {
    setEditId(prog.id);
    setForm({
      department:      prog.department,
      name:            prog.name,
      code:            prog.code,
      specialization:  prog.specialization || "",
      total_years:     prog.total_years,
      total_semesters: prog.total_semesters,
    });
    setError(""); setSuccess("");
    window.scrollTo({ top: 0, behavior: "smooth" });
  };

  const cancelEdit = () => {
    setEditId(null);
    setForm(INITIAL_FORM);
    setError(""); setSuccess("");
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this program? This will also remove all its terms, sections, course offerings, and timetables.")) return;
    try {
      await api.delete(`academics/programs/${id}/`);
      loadAll();
    } catch (err) {
      setError(extractError(err, "Failed to delete program."));
    }
  };

  /* ── Search filter + group by department ────── */
  const groupedPrograms = useMemo(() => {
    const q = search.toLowerCase();
    const filtered = q
      ? programs.filter(
          (p) =>
            (p.display_name || p.name || "").toLowerCase().includes(q) ||
            (p.code || "").toLowerCase().includes(q) ||
            (p.specialization || "").toLowerCase().includes(q) ||
            (p.department_name || "").toLowerCase().includes(q)
        )
      : programs;

    // Group into { deptName -> [prog, ...] }
    const map = {};
    filtered.forEach((p) => {
      const key = p.department_name || "Other / Unassigned";
      if (!map[key]) map[key] = [];
      map[key].push(p);
    });

    // Sort dept names alphabetically, programs inside by code
    return Object.entries(map)
      .sort(([a], [b]) => a.localeCompare(b))
      .map(([dept, progs]) => ({
        dept,
        progs: [...progs].sort((a, b) => (a.code || "").localeCompare(b.code || "")),
      }));
  }, [programs, search]);

  const totalFiltered = groupedPrograms.reduce((s, g) => s + g.progs.length, 0);

  return (
    <DashboardLayout>
      {/* ── Page Head ── */}
      <div className="page-head">
        <h1>Program Management</h1>
        <p>Create and manage academic programs, organised by department.</p>
      </div>

      {/* ── Bulk Upload ── */}
      <BulkUploadCard
        title="Upload Programs"
        endpoint="academics/programs/bulk-upload/"
        useFileUpload
        requiredColumns={["name", "code", "department_code"]}
        templateFileName="programs-upload-template.xlsx"
        templateSampleRow={{
          name: "BTech",
          code: "BTech CSE",
          specialization: "Computer Science",
          department_code: "CSE",
          total_years: 4,
          total_semesters: 8,
        }}
        onUploadComplete={loadAll}
      />

      {/* ── Two-column: Form left | Programs right ── */}
      <div className="faculty-two-col">

        {/* ── LEFT: Add / Edit Form ── */}
        <section className="data-card faculty-form-card">
          <h3>
            <FaUniversity style={{ marginRight: 8, color: "var(--brand)" }} />
            {editId ? "Update Program" : "Add New Program"}
          </h3>

          {error   && <p className="upload-error">{error}</p>}
          {success && <p className="upload-success">{success}</p>}

          <form className="faculty-register-form" onSubmit={handleSubmit}>
            {/* Department */}
            <div className="form-group">
              <label className="form-label">Department *</label>
              <select
                className="input"
                value={form.department}
                onChange={(e) => setForm((p) => ({ ...p, department: e.target.value }))}
                required
              >
                <option value="">— Choose department —</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.code})
                  </option>
                ))}
              </select>
            </div>

            {/* Name */}
            <div className="form-group">
              <label className="form-label">Program Name *</label>
              <input
                className="input"
                placeholder="e.g. BTech, BCA, MCA"
                value={form.name}
                onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                required
              />
              <span className="input-hint">Degree level — BTech, BCA, MCA, BSc, MTech etc.</span>
            </div>

            {/* Specialization */}
            <div className="form-group">
              <label className="form-label">Specialization</label>
              <input
                className="input"
                placeholder="e.g. Computer Science, AIML, Full Stack"
                value={form.specialization}
                onChange={(e) => setForm((p) => ({ ...p, specialization: e.target.value }))}
              />
              <span className="input-hint">Leave blank for programs without a specialization (e.g. BCA, MCA)</span>
            </div>

            {/* Code */}
            <div className="form-group">
              <label className="form-label">Program Code *</label>
              <input
                className="input"
                placeholder="e.g. BTech CSE, BCA (FSD)"
                value={form.code}
                onChange={(e) => setForm((p) => ({ ...p, code: e.target.value }))}
                required
              />
              <span className="input-hint">Unique identifier used in course assignments and timetables</span>
            </div>

            {/* Years + Semesters */}
            <div style={{ display: "flex", gap: 12 }}>
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Total Years *</label>
                <input
                  className="input"
                  type="number"
                  min="1" max="6"
                  value={form.total_years}
                  onChange={(e) => setForm((p) => ({ ...p, total_years: e.target.value }))}
                  required
                />
              </div>
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Total Semesters *</label>
                <input
                  className="input"
                  type="number"
                  min="1" max="12"
                  value={form.total_semesters}
                  onChange={(e) => setForm((p) => ({ ...p, total_semesters: e.target.value }))}
                  required
                />
              </div>
            </div>

            <div className="form-group form-group-btn" style={{ display: "flex", gap: 10 }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={submitting}
                style={{ flex: 1, justifyContent: "center" }}
              >
                <FaGraduationCap style={{ marginRight: 8 }} />
                {submitting ? "Saving…" : editId ? "Update Program" : "Create Program"}
              </button>
              {editId && (
                <button type="button" className="btn btn-secondary" onClick={cancelEdit}>
                  <FaTimes />
                </button>
              )}
            </div>
          </form>
        </section>

        {/* ── RIGHT: Department-grouped Program List ── */}
        <section className="data-card faculty-list-card" style={{ padding: 0, overflow: "hidden" }}>
          {/* Panel header */}
          <div className="prog-list-header">
            <div>
              <h3 style={{ margin: 0, fontSize: 16, fontWeight: 700, color: "var(--text)" }}>
                Programs
              </h3>
              <p style={{ margin: "2px 0 0", fontSize: 12, color: "var(--muted)" }}>
                {programs.length} programs across {Object.keys(
                  programs.reduce((m, p) => { m[p.department_name || "Other"] = 1; return m; }, {})
                ).length} departments
              </p>
            </div>
            {/* Search */}
            <div className="pdc-search-wrap">
              <FaSearch className="pdc-search-icon" />
              <input
                className="input pdc-search-input"
                placeholder="Search programs…"
                value={search}
                onChange={(e) => setSearch(e.target.value)}
              />
            </div>
          </div>

          {/* Body */}
          <div className="dept-list-body">
            {loading ? (
              <p className="upload-help" style={{ padding: "20px 20px" }}>Loading programs…</p>
            ) : totalFiltered === 0 ? (
              <p className="upload-help" style={{ padding: "20px 20px" }}>
                {search ? "No programs match your search." : "No programs yet. Add one using the form."}
              </p>
            ) : (
              groupedPrograms.map(({ dept, progs }) => (
                <DeptSection
                  key={dept}
                  deptName={dept}
                  programs={progs}
                  onEdit={handleEdit}
                  onDelete={handleDelete}
                />
              ))
            )}
          </div>
        </section>
      </div>
    </DashboardLayout>
  );
}

export default ProgramsPage;
