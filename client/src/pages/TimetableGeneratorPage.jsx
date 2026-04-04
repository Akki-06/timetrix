import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import { asList, extractError } from "../utils/helpers";
import { FaMagic, FaUsers, FaCheckCircle, FaExclamationTriangle, FaArrowRight } from "react-icons/fa";

// Derive academic year from semester: sem 1-2 → Year 1, sem 3-4 → Year 2 …
function yearFromSemester(sem) {
  return Math.ceil(sem / 2);
}

function TimetableGeneratorPage() {
  const navigate = useNavigate();

  const [programs, setPrograms]       = useState([]);
  const [timetables, setTimetables]   = useState([]);
  const [sections, setSections]       = useState([]);   // preview for selected prog+sem

  const [selectedProgramId, setSelectedProgramId] = useState("");
  const [selectedSemester,  setSelectedSemester]  = useState("");

  const [pageLoading,    setPageLoading]    = useState(true);
  const [sectionsLoading, setSectionsLoading] = useState(false);
  const [generating,     setGenerating]     = useState(false);
  const [result,         setResult]         = useState(null);
  const [error,          setError]          = useState("");

  // ── initial load ────────────────────────────────────────────────────────
  const loadBase = useCallback(async () => {
    try {
      setPageLoading(true);
      const [progResp, ttResp] = await Promise.all([
        api.get("academics/programs/"),
        api.get("scheduler/timetables/", { params: { ordering: "-created_at" } }),
      ]);
      setPrograms(asList(progResp.data));
      setTimetables(asList(ttResp.data));
    } catch {
      setError("Failed to load data. Check backend connection.");
    } finally {
      setPageLoading(false);
    }
  }, []);

  useEffect(() => { loadBase(); }, [loadBase]);

  // ── load sections preview whenever program+semester changes ─────────────
  useEffect(() => {
    if (!selectedProgramId || !selectedSemester) {
      setSections([]);
      return;
    }
    const load = async () => {
      setSectionsLoading(true);
      try {
        const resp = await api.get("academics/student-groups/", {
          params: {
            "term__program":  selectedProgramId,
            "term__semester": selectedSemester,
          },
        });
        setSections(asList(resp.data).sort((a, b) => a.name.localeCompare(b.name)));
      } catch {
        setSections([]);
      } finally {
        setSectionsLoading(false);
      }
    };
    load();
  }, [selectedProgramId, selectedSemester]);

  // ── selected program object ──────────────────────────────────────────────
  const selectedProgram = useMemo(
    () => programs.find((p) => String(p.id) === String(selectedProgramId)) || null,
    [programs, selectedProgramId]
  );

  // Semester options: 1 … total_semesters of selected program
  const semesterOptions = useMemo(() => {
    if (!selectedProgram) return [];
    return Array.from({ length: selectedProgram.total_semesters || 8 }, (_, i) => i + 1);
  }, [selectedProgram]);

  // ── generate ─────────────────────────────────────────────────────────────
  const handleGenerate = async () => {
    if (!selectedProgramId || !selectedSemester || sections.length === 0) return;
    setGenerating(true);
    setError("");
    setResult(null);

    try {
      const resp = await api.post("scheduler/generate/", {
        program_id: Number(selectedProgramId),
        semester:   Number(selectedSemester),
      }, { timeout: 120000 });

      const data = resp.data;
      setResult(data);

      // Refresh history
      const ttResp = await api.get("scheduler/timetables/", { params: { ordering: "-created_at" } });
      setTimetables(asList(ttResp.data));

      // If allocations were saved, navigate to timetables page after 2s
      if (data.allocations > 0) {
        setTimeout(() => navigate("/generated"), 2000);
      }
    } catch (err) {
      // Try to extract the response body even on error status codes
      const errData = err?.response?.data;
      if (errData && errData.status) {
        setResult(errData);
      } else {
        setError(extractError(err, "Generation failed. Check server logs."));
      }
      // Refresh history even on error (timetable record may exist)
      try {
        const ttResp = await api.get("scheduler/timetables/", { params: { ordering: "-created_at" } });
        setTimetables(asList(ttResp.data));
      } catch { /* ignore */ }
    } finally {
      setGenerating(false);
    }
  };

  const handleProgramChange = (val) => {
    setSelectedProgramId(val);
    setSelectedSemester("");
    setResult(null);
    setError("");
    setSections([]);
  };

  // ── timetable history enriched with program name ─────────────────────────
  const programMap = useMemo(
    () => Object.fromEntries(programs.map((p) => [p.id, p])),
    [programs]
  );

  if (pageLoading) {
    return (
      <DashboardLayout>
        <div className="page-head">
          <h1>Timetable Generator</h1>
          <p className="upload-help">Loading...</p>
        </div>
      </DashboardLayout>
    );
  }

  const canGenerate = selectedProgramId && selectedSemester && sections.length > 0 && !generating;
  const derivedYear = selectedSemester ? yearFromSemester(Number(selectedSemester)) : null;

  return (
    <DashboardLayout>
      <div className="page-head">
        <h1>Timetable Generator</h1>
        <p>
          Select a program and semester — the scheduler will assign rooms, time slots,
          and faculty for every registered section automatically.
        </p>
      </div>

      <div className="generator-grid">

        {/* ── LEFT: Parameters ─────────────────────────────────────────────── */}
        <section className="data-card generator-params-card">
          <h3>Generation Parameters</h3>

          {/* Program */}
          <div className="generator-fields">
            <label className="generator-label">Program *</label>
            <select
              className="input"
              value={selectedProgramId}
              onChange={(e) => handleProgramChange(e.target.value)}
            >
              <option value="">Select program</option>
              {programs.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.display_name || p.name} ({p.code})
                </option>
              ))}
            </select>
          </div>

          {/* Semester — shown as "Semester 1", "Semester 2" … based on program duration */}
          <div className="generator-fields">
            <label className="generator-label">Semester *</label>
            <select
              className="input"
              value={selectedSemester}
              onChange={(e) => { setSelectedSemester(e.target.value); setResult(null); setError(""); }}
              disabled={!selectedProgramId}
            >
              <option value="">
                {selectedProgramId ? "Select semester" : "Select program first"}
              </option>
              {semesterOptions.map((s) => (
                <option key={s} value={s}>
                  Semester {s}  (Year {yearFromSemester(s)})
                </option>
              ))}
            </select>
          </div>

          {/* Year derived info */}
          {selectedSemester && (
            <p className="input-hint" style={{ marginBottom: 12 }}>
              Academic year <strong>Year {derivedYear}</strong> of{" "}
              {selectedProgram?.display_name || selectedProgram?.name}
            </p>
          )}

          {/* Sections preview */}
          {selectedProgramId && selectedSemester && (
            <div style={{
              background: "var(--sidebar-bg, rgba(0,0,0,0.04))",
              borderRadius: 8, padding: 12, marginBottom: 16,
              border: "1px solid var(--border)",
            }}>
              <p style={{ fontSize: "0.8rem", fontWeight: 600, marginBottom: 6, color: "var(--muted)" }}>
                SECTIONS TO BE SCHEDULED
              </p>
              {sectionsLoading ? (
                <p className="upload-help" style={{ margin: 0 }}>Loading sections...</p>
              ) : sections.length === 0 ? (
                <p style={{ color: "#ef4444", fontSize: "0.85rem", margin: 0 }}>
                  No sections registered for{" "}
                  {selectedProgram?.display_name} Sem {selectedSemester}.{" "}
                  <a href="/sections" style={{ color: "var(--brand)" }}>Register sections first →</a>
                </p>
              ) : (
                <>
                  <p style={{ fontSize: "0.8rem", color: "var(--muted)", marginBottom: 8 }}>
                    {sections.length} section{sections.length > 1 ? "s" : ""} found — all will be scheduled in this run
                  </p>
                  <div style={{ display: "flex", flexWrap: "wrap", gap: 8 }}>
                    {sections.map((s) => (
                      <div key={s.id} style={{
                        background: "var(--card-bg)", border: "1px solid var(--border)",
                        borderRadius: 6, padding: "4px 10px", fontSize: "0.82rem",
                        display: "flex", alignItems: "center", gap: 6,
                      }}>
                        <FaUsers style={{ color: "var(--brand)", fontSize: 11 }} />
                        <strong>Section {s.name}</strong>
                        <span style={{ color: "var(--muted)" }}>{s.strength} students</span>
                      </div>
                    ))}
                  </div>
                </>
              )}
            </div>
          )}

          <button
            type="button"
            className="btn-primary generator-btn"
            onClick={handleGenerate}
            disabled={!canGenerate}
          >
            <FaMagic style={{ marginRight: 6 }} />
            {generating
              ? `Scheduling ${sections.length} section${sections.length > 1 ? "s" : ""}...`
              : "Generate Timetable"}
          </button>

          {error && <p className="upload-error generator-error">{error}</p>}

          {/* Result card */}
          {result && (
            <div style={{ marginTop: 16 }}>
              <div style={{
                display: "flex", alignItems: "center", gap: 8, marginBottom: 10,
                color: result.status === "success" ? "var(--brand)"
                     : result.status === "partial"  ? "#f59e0b"
                     : "#ef4444",
                fontWeight: 600, fontSize: "0.9rem",
              }}>
                {result.status === "success"
                  ? <FaCheckCircle />
                  : <FaExclamationTriangle />}
                {result.status === "success" ? "Fully Scheduled"
               : result.status === "partial"  ? "Partially Scheduled"
               : `Generation Failed: ${result.reason || "unknown error"}`}
              </div>

              <div className="generator-result">
                <div><span>Allocations</span><strong>{result.allocations ?? 0}</strong></div>
                <div><span>Avg Score</span><strong>
                  {result.avg_score != null ? Number(result.avg_score).toFixed(3) : "N/A"}
                </strong></div>
                <div><span>ML Used</span><strong>{result.ml_used ? "Yes" : "No"}</strong></div>
              </div>

              {(result.allocations ?? 0) > 0 && (
                <button
                  type="button"
                  className="btn-primary"
                  style={{ marginTop: 12, width: "100%", display: "flex", alignItems: "center", justifyContent: "center", gap: 6 }}
                  onClick={() => navigate("/generated")}
                >
                  <FaArrowRight style={{ fontSize: 12 }} />
                  View Timetable
                </button>
              )}

              {/* Per-section breakdown */}
              {Array.isArray(result.sections) && result.sections.length > 0 && (
                <div style={{ marginTop: 12 }}>
                  <p style={{ fontSize: "0.78rem", color: "var(--muted)", fontWeight: 600, marginBottom: 6 }}>
                    PER-SECTION RESULT
                  </p>
                  <div className="table-wrap" style={{ fontSize: "0.85rem" }}>
                    <table>
                      <thead>
                        <tr>
                          <th>Section</th>
                          <th>Strength</th>
                          <th>Sessions</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.sections.map((s) => (
                          <tr key={s.section}>
                            <td><strong>Section {s.section}</strong></td>
                            <td>{s.strength}</td>
                            <td>
                              <span style={{ color: s.allocated > 0 ? "var(--brand)" : "#ef4444" }}>
                                {s.allocated} scheduled
                              </span>
                            </td>
                          </tr>
                        ))}
                      </tbody>
                    </table>
                  </div>
                </div>
              )}
            </div>
          )}
        </section>

        {/* ── RIGHT: Generation History ────────────────────────────────────── */}
        <section className="data-card generator-history-card">
          <h3>Generation History</h3>
          <p className="upload-help">Previously generated timetables.</p>

          {timetables.length === 0 ? (
            <p className="upload-help">No generation history yet.</p>
          ) : (
            <div className="history-list">
              {timetables.map((tt) => {
                // Enrich from known programs (best-effort — term info not always in list)
                const createdAt = tt.created_at ? new Date(tt.created_at) : null;
                return (
                  <article key={tt.id} className="history-item">
                    <div className="history-main">
                      <h4>
                        {tt.program_code
                          ? `${tt.program_code} Sem ${tt.semester}`
                          : tt.program_name
                            ? `${tt.program_name} Sem ${tt.semester}`
                            : `Term #${tt.term}`
                        }{" "}— v{tt.version}
                        {tt.is_finalized && (
                          <span style={{
                            marginLeft: 8, fontSize: "0.7rem", background: "var(--brand)",
                            color: "#fff", borderRadius: 4, padding: "1px 6px",
                          }}>
                            FINAL
                          </span>
                        )}
                      </h4>
                      <p style={{ color: "var(--muted)", fontSize: "0.8rem" }}>
                        Score: {tt.total_constraint_score?.toFixed(3) ?? "—"}
                      </p>
                    </div>
                    <div className="history-meta">
                      <small>
                        {createdAt
                          ? createdAt.toLocaleDateString("en-IN", {
                              day: "2-digit", month: "short", year: "numeric",
                            })
                          : "—"}
                      </small>
                      <small style={{ color: "var(--muted)" }}>
                        {createdAt
                          ? createdAt.toLocaleTimeString("en-IN", { hour: "2-digit", minute: "2-digit" })
                          : ""}
                      </small>
                    </div>
                  </article>
                );
              })}
            </div>
          )}
        </section>
      </div>

      {/* Unscheduled items */}
      {result && Array.isArray(result.unscheduled) && result.unscheduled.length > 0 && (
        <section className="data-card" style={{ marginTop: 0 }}>
          <h3>Unscheduled Items ({result.unscheduled.length})</h3>
          <p className="upload-help">
            These could not be placed due to room/faculty/slot conflicts.
            Check that rooms, faculty, and course offerings are properly configured.
          </p>
          <div className="upload-partial">
            <ul>
              {result.unscheduled.map((item, idx) => (
                <li key={idx}>{item}</li>
              ))}
            </ul>
          </div>
        </section>
      )}
    </DashboardLayout>
  );
}

export default TimetableGeneratorPage;
