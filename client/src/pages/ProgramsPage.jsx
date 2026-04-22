import { useCallback, useEffect, useState, useMemo } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import BulkUploadCard from "../components/BulkUploadCard";
import { asList, extractError } from "../utils/helpers";
import {
  FaUniversity, FaTrash, FaEdit, FaTimes, FaPlus,
  FaGraduationCap, FaLayerGroup, FaCalendarAlt, FaSearch,
  FaChevronDown, FaChevronRight,
} from "react-icons/fa";

const INITIAL_FORM = {
  department: "",
  name: "",
  code: "",
  specialization: "",
  total_years: 4,
  total_semesters: 8,
};

function ProgramsPage() {
  const [programs, setPrograms] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");
  const [form, setForm] = useState(INITIAL_FORM);
  const [editId, setEditId] = useState(null);
  const [showForm, setShowForm] = useState(false);
  const [search, setSearch] = useState("");
  const [expandedDepts, setExpandedDepts] = useState({});

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

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError(""); setSuccess(""); setSubmitting(true);
    try {
      const payload = {
        name: form.name.trim(),
        code: form.code.trim(),
        department: Number(form.department),
        specialization: form.specialization.trim(),
        total_years: Number(form.total_years),
        total_semesters: Number(form.total_semesters),
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
      setShowForm(false);
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
      department: prog.department,
      name: prog.name,
      code: prog.code,
      specialization: prog.specialization || "",
      total_years: prog.total_years,
      total_semesters: prog.total_semesters,
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
    if (!window.confirm("Delete this program? This will also remove all its terms, sections, course offerings, and timetables.")) return;
    try {
      await api.delete(`academics/programs/${id}/`);
      loadAll();
    } catch (err) {
      setError(extractError(err, "Failed to delete program."));
    }
  };

  /* Group by department */
  const grouped = useMemo(() => {
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

    const map = {};
    filtered.forEach((p) => {
      const key = p.department_name || "Other / Unassigned";
      if (!map[key]) map[key] = { name: key, programs: [], totalYears: 0 };
      map[key].programs.push(p);
      map[key].totalYears += p.total_years || 0;
    });

    return Object.values(map)
      .sort((a, b) => a.name.localeCompare(b.name))
      .map((g) => ({ ...g, programs: g.programs.sort((a, b) => (a.code || "").localeCompare(b.code || "")) }));
  }, [programs, search]);

  const toggleDept = (name) => setExpandedDepts((p) => ({ ...p, [name]: !p[name] }));



  const deptCount = Object.keys(
    programs.reduce((m, p) => { m[p.department_name || "Other"] = 1; return m; }, {})
  ).length;

  return (
    <DashboardLayout>
      {/* Header */}
      <div className="sec-page-header">
        <div>
          <h1 className="sec-page-title">Programs</h1>
          <p className="sec-page-sub">
            Manage academic programs organised by department. Programs define the
            degree structure used for course assignments and timetables.
          </p>
        </div>
        <button className="sec-add-btn" onClick={() => { setShowForm(!showForm); setEditId(null); setForm(INITIAL_FORM); }}>
          {showForm ? <><FaTimes /> Close</> : <><FaPlus /> Add Program</>}
        </button>
      </div>

      {/* Alerts */}
      {error && <div className="sec-alert sec-alert-error">{error}</div>}
      {success && <div className="sec-alert sec-alert-success">{success}</div>}

      {/* Form Panel */}
      {showForm && (
        <div className="sec-form-panel">
          <div className="sec-form-header">
            <h3>{editId ? "Update Program" : "Register New Program"}</h3>
          </div>
          <form className="sec-form-grid" onSubmit={handleSubmit}>
            <div className="sec-field">
              <label>Department <span className="sec-req">*</span></label>
              <select
                value={form.department}
                onChange={(e) => setForm((p) => ({ ...p, department: e.target.value }))}
                required
              >
                <option value="">Choose department</option>
                {[...departments].sort((a, b) => a.name.localeCompare(b.name)).map((d) => (
                  <option key={d.id} value={d.id}>{d.name} ({d.code})</option>
                ))}
              </select>
            </div>

            <div className="sec-field">
              <label>Program Name <span className="sec-req">*</span></label>
              <input
                placeholder="e.g. BTech, BCA, MCA"
                value={form.name}
                onChange={(e) => setForm((p) => ({ ...p, name: e.target.value }))}
                required
              />
            </div>

            <div className="sec-field">
              <label>Program Code <span className="sec-req">*</span></label>
              <input
                placeholder="e.g. BTech CSE, BCA (FSD)"
                value={form.code}
                onChange={(e) => setForm((p) => ({ ...p, code: e.target.value }))}
                required
              />
            </div>

            <div className="sec-field">
              <label>Specialization <span className="sec-opt">(optional)</span></label>
              <input
                placeholder="e.g. Computer Science, AIML"
                value={form.specialization}
                onChange={(e) => setForm((p) => ({ ...p, specialization: e.target.value }))}
              />
            </div>

            <div className="sec-field">
              <label>Total Years <span className="sec-req">*</span></label>
              <input
                type="number" min="1" max="6"
                value={form.total_years}
                onChange={(e) => setForm((p) => ({ ...p, total_years: e.target.value }))}
                required
              />
            </div>

            <div className="sec-field">
              <label>Total Semesters <span className="sec-req">*</span></label>
              <input
                type="number" min="1" max="12"
                value={form.total_semesters}
                onChange={(e) => setForm((p) => ({ ...p, total_semesters: e.target.value }))}
                required
              />
            </div>

            <div className="sec-form-actions">
              <button type="submit" className="sec-submit-btn" disabled={submitting}>
                {submitting ? "Saving..." : editId ? "Update Program" : "Create Program"}
              </button>
              {editId && (
                <button type="button" className="sec-cancel-btn" onClick={cancelEdit}>Cancel</button>
              )}
            </div>
          </form>
        </div>
      )}

      {/* Bulk Upload */}
      <BulkUploadCard
        title="Upload Programs"
        endpoint="academics/programs/bulk-upload/"
        useFileUpload
        requiredColumns={["name", "code", "department_code"]}
        templateFileName="programs-upload-template.xlsx"
        templateSampleRow={{
          name: "BTech", code: "BTech CSE", specialization: "Computer Science",
          department_code: "CSE", total_years: 4, total_semesters: 8,
        }}
        onUploadComplete={loadAll}
      />

      {/* Content */}
      {loading ? (
        <div className="sec-loading">
          <div className="sec-loading-spinner" />
          Loading programs...
        </div>
      ) : programs.length === 0 ? (
        <div className="sec-empty">
          <FaGraduationCap className="sec-empty-icon" />
          <h3>No programs registered yet</h3>
          <p>Click "Add Program" to register your first academic program.</p>
        </div>
      ) : (
        <div className="sec-hierarchy">
          {/* Summary strip */}
          <div className="sec-summary-strip">
            <div className="sec-summary-item">
              <FaUniversity />
              <span><strong>{deptCount}</strong> Departments</span>
            </div>
            <div className="sec-summary-item">
              <FaGraduationCap />
              <span><strong>{programs.length}</strong> Programs</span>
            </div>
            {search && (
              <div style={{ marginLeft: "auto" }}>
                <div className="pdc-search-wrap">
                  <FaSearch className="pdc-search-icon" />
                  <input
                    className="input pdc-search-input"
                    placeholder="Search programs..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
              </div>
            )}
            {!search && (
              <div style={{ marginLeft: "auto" }}>
                <div className="pdc-search-wrap">
                  <FaSearch className="pdc-search-icon" />
                  <input
                    className="input pdc-search-input"
                    placeholder="Search programs..."
                    value={search}
                    onChange={(e) => setSearch(e.target.value)}
                  />
                </div>
              </div>
            )}
          </div>

          {/* Department accordion */}
          {grouped.map((group) => (
            <div key={group.name} className="sec-program-block">
              <button className="sec-program-header" onClick={() => toggleDept(group.name)}>
                <div className="sec-program-left">
                  {expandedDepts[group.name] ? <FaChevronDown size={12} /> : <FaChevronRight size={12} />}
                  <div className="sec-program-icon">
                    <FaUniversity />
                  </div>
                  <div>
                    <span className="sec-program-name">{group.name}</span>
                  </div>
                </div>
                <div className="sec-program-meta">
                  <span className="sec-meta-badge">{group.programs.length} programs</span>
                </div>
              </button>

              {expandedDepts[group.name] && (
                <div className="sec-years-container">
                  <div className="sec-cards-grid">
                    {group.programs.map((prog) => (
                      <div key={prog.id} className="sec-card">
                        <div className="sec-card-top">
                          <div className="sec-card-name-row">
                            <span className="sec-card-name">{prog.display_name || prog.name}</span>
                            <span className="sec-card-sem-badge">{prog.code}</span>
                          </div>
                          <div className="sec-card-actions">
                            <button className="sec-icon-btn" title="Edit" onClick={() => handleEdit(prog)}>
                              <FaEdit />
                            </button>
                            <button className="sec-icon-btn sec-icon-danger" title="Delete" onClick={() => handleDelete(prog.id)}>
                              <FaTrash />
                            </button>
                          </div>
                        </div>

                        <div className="sec-card-details">
                          {prog.specialization && (
                            <div className="sec-detail-row">
                              <span className="sec-detail-label">Specialization</span>
                              <span className="sec-detail-value">{prog.specialization}</span>
                            </div>
                          )}
                          <div className="sec-detail-row">
                            <span className="sec-detail-label">Duration</span>
                            <span className="sec-detail-value">
                              {prog.total_years} years · {prog.total_semesters} semesters
                            </span>
                          </div>
                        </div>
                      </div>
                    ))}
                  </div>
                </div>
              )}
            </div>
          ))}
        </div>
      )}
    </DashboardLayout>
  );
}

export default ProgramsPage;
