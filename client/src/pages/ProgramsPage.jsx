import { useCallback, useEffect, useState } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import BulkUploadCard from "../components/BulkUploadCard";
import { toNumber } from "../utils/spreadsheet";
import { asList, extractError } from "../utils/helpers";
import { FaBook, FaTrash, FaUniversity, FaEdit, FaTimes } from "react-icons/fa";

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

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const [editId, setEditId] = useState(null);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSubmitting(true);

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
    if (!window.confirm("Delete this program? This will also remove all its terms, sections, course offerings, and timetables.")) return;
    try {
      await api.delete(`academics/programs/${id}/`);
      loadAll();
    } catch (err) {
      setError(extractError(err, "Failed to delete program."));
    }
  };

  return (
    <DashboardLayout>
      <div className="page-head">
        <h1>Program Management</h1>
        <p>Create and manage academic programs under departments.</p>
      </div>

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

      <div className="faculty-two-col">
        {/* ── LEFT: Add Program Form ── */}
        <section className="data-card faculty-form-card">
          <h3>
            <FaUniversity style={{ marginRight: 8, color: "var(--brand)" }} />
            {editId ? "Update Program" : "Add New Program"}
          </h3>

          {error && <p className="upload-error">{error}</p>}
          {success && <p className="upload-success">{success}</p>}

          <form className="faculty-register-form" onSubmit={handleSubmit}>
            {/* Department */}
            <div className="form-group">
              <label className="form-label">Department *</label>
              <select
                className="input"
                value={form.department}
                onChange={(e) =>
                  setForm((p) => ({ ...p, department: e.target.value }))
                }
                required
              >
                <option value="">Choose department</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name} ({d.code})
                  </option>
                ))}
              </select>
            </div>

            {/* Program Name */}
            <div className="form-group">
              <label className="form-label">Program Name *</label>
              <input
                className="input"
                placeholder="e.g. BTech, BCA, MCA"
                value={form.name}
                onChange={(e) =>
                  setForm((p) => ({ ...p, name: e.target.value }))
                }
                required
              />
              <span className="input-hint">
                Degree name — BTech, BCA, MCA, BSc, MTech etc.
              </span>
            </div>

            {/* Specialization */}
            <div className="form-group">
              <label className="form-label">Specialization</label>
              <input
                className="input"
                placeholder="e.g. Computer Science, AIML, Cyber Security"
                value={form.specialization}
                onChange={(e) =>
                  setForm((p) => ({ ...p, specialization: e.target.value }))
                }
              />
              <span className="input-hint">
                Leave blank for programs without specialization (e.g. BCA, MCA)
              </span>
            </div>

            {/* Code */}
            <div className="form-group">
              <label className="form-label">Program Code *</label>
              <input
                className="input"
                placeholder="e.g. BTech CSE, BCA, MCA"
                value={form.code}
                onChange={(e) =>
                  setForm((p) => ({ ...p, code: e.target.value }))
                }
                required
              />
              <span className="input-hint">
                Unique short code used in course assignments and timetables
              </span>
            </div>

            {/* Years and Semesters side by side */}
            <div style={{ display: "flex", gap: 12 }}>
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Total Years *</label>
                <input
                  className="input"
                  type="number"
                  min="1"
                  max="6"
                  value={form.total_years}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, total_years: e.target.value }))
                  }
                  required
                />
              </div>
              <div className="form-group" style={{ flex: 1 }}>
                <label className="form-label">Total Semesters *</label>
                <input
                  className="input"
                  type="number"
                  min="1"
                  max="12"
                  value={form.total_semesters}
                  onChange={(e) =>
                    setForm((p) => ({ ...p, total_semesters: e.target.value }))
                  }
                  required
                />
              </div>
            </div>

            <div className="form-group form-group-btn">
              <div className="form-actions" style={{ display: "flex", gap: "10px" }}>
              <button
                type="submit"
                className="btn btn-primary"
                disabled={submitting}
                style={{ flex: 1 }}
              >
                {submitting ? "Saving..." : editId ? "Update Program" : "Create Program"}
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
            </div>
          </form>
        </section>

        {/* ── RIGHT: Existing Programs ── */}
        <section className="data-card faculty-list-card">
          <h3>Existing Programs ({programs.length})</h3>
          {loading ? (
            <p className="upload-help">Loading programs...</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Code</th>
                    <th>Program</th>
                    <th>Department</th>
                    <th>Duration</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {programs.length === 0 ? (
                    <tr>
                      <td
                        colSpan="5"
                        style={{
                          textAlign: "center",
                          color: "var(--muted)",
                          padding: 24,
                        }}
                      >
                        No programs yet. Add one using the form.
                      </td>
                    </tr>
                  ) : (
                    programs.map((p) => (
                      <tr key={p.id}>
                        <td>
                          <strong>{p.code}</strong>
                        </td>
                        <td>
                          <div className="fac-name-cell">
                            <FaUniversity
                              style={{
                                color: "var(--brand)",
                                flexShrink: 0,
                              }}
                            />
                            <span>{p.display_name}</span>
                          </div>
                        </td>
                        <td>
                          {p.department_name || (
                            <span style={{ color: "var(--muted)" }}>—</span>
                          )}
                        </td>
                        <td>
                          {p.total_years} yrs / {p.total_semesters} sem
                        </td>
                        <td>
                          <div className="table-actions">
                            <button
                              className="action-btn"
                              onClick={() => handleEdit(p)}
                              title="Edit Program"
                            >
                              <FaEdit style={{ color: "#3b82f6" }} />
                            </button>
                            <button
                              className="action-btn"
                              onClick={() => handleDelete(p.id)}
                              title="Delete Program"
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
        </section>
      </div>
    </DashboardLayout>
  );
}

export default ProgramsPage;
