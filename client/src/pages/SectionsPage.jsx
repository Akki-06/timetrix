import { useCallback, useEffect, useState, useMemo } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import BulkUploadCard from "../components/BulkUploadCard";
import { toNumber } from "../utils/spreadsheet";
import { asList, extractError } from "../utils/helpers";
import { FaUsers, FaTrash } from "react-icons/fa";

const INITIAL_FORM = {
  program: "",
  semester: "",
  section: "",
  strength: 45,
  description: "",
};

function SectionsPage() {
  const [groups, setGroups]       = useState([]);
  const [programs, setPrograms]   = useState([]);
  const [loading, setLoading]     = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError]         = useState("");
  const [success, setSuccess]     = useState("");
  const [form, setForm]           = useState(INITIAL_FORM);

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
      await api.post("academics/student-groups/quick-create/", {
        program:     Number(form.program),
        semester:    Number(form.semester),
        section:     form.section.trim().toUpperCase(),
        strength:    Number(form.strength),
        description: form.description.trim(),
      });

      setForm(INITIAL_FORM);
      setSuccess("Section registered successfully.");
      loadAll();
    } catch (err) {
      setError(extractError(err, "Failed to register section."));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    if (!window.confirm("Delete this section? Associated course offerings and allocations will also be removed.")) return;
    try {
      await api.delete(`academics/student-groups/${id}/`);
      loadAll();
    } catch (err) {
      setError(extractError(err, "Failed to delete section."));
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
          if (!prog) {
            throw new Error(
              `Program code '${progCode}' not found. Add the program first.`
            );
          }
          return {
            program:     prog.id,
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
            Register Section
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

            <div className="form-group form-group-btn">
              <button
                type="submit"
                className="btn-primary btn-with-icon"
                disabled={submitting}
                style={{ width: "100%", justifyContent: "center" }}
              >
                <FaUsers />
                {submitting ? "Registering..." : "Register Section"}
              </button>
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
                      <tr key={g.id}>
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
                          <strong>{g.name}</strong>
                        </td>
                        <td>{g.strength}</td>
                        <td style={{ color: "var(--muted)", fontSize: "0.85em" }}>
                          {g.description || "—"}
                        </td>
                        <td>
                          <button
                            className="icon-btn danger"
                            title="Delete"
                            onClick={() => handleDelete(g.id)}
                          >
                            <FaTrash />
                          </button>
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

export default SectionsPage;
