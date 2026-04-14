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

  // PE elective slot group state: { [offeringId]: groupToken }
  const [peOfferings,        setPeOfferings]        = useState([]);  // raw offering objects
  const [peSlotGroups,       setPeSlotGroups]        = useState({});  // { id: string }
  const [peEnabled,          setPeEnabled]           = useState({});  // { id: boolean } — false = skip PE parallel logic
  const [peGroupSaving,      setPeGroupSaving]       = useState(false);

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

  // ── load sections + PE offerings whenever program+semester changes ───────
  useEffect(() => {
    if (!selectedProgramId || !selectedSemester) {
      setSections([]);
      setPeOfferings([]);
      setPeSlotGroups({});
      setPeEnabled({});
      return;
    }
    const load = async () => {
      setSectionsLoading(true);
      try {
        // Load sections and PE course-offerings in parallel
        const [sgResp, peResp] = await Promise.all([
          api.get("academics/student-groups/", {
            params: {
              "term__program":  selectedProgramId,
              "term__semester": selectedSemester,
            },
          }),
          api.get("academics/course-offerings/", {
            params: {
              "student_group__term__program":  selectedProgramId,
              "student_group__term__semester": selectedSemester,
              "course__course_type":           "PE",
            },
          }),
        ]);
        setSections(asList(sgResp.data).sort((a, b) => a.name.localeCompare(b.name)));

        // Deduplicate PE offerings by course (show one row per unique PE course)
        // Also exclude placeholder PE courses like "Programme Elective-I" — show only real options
        const allPe = asList(peResp.data);
        const seen  = new Set();
        const uniquePe = allPe.filter((o) => {
          const name = (o.course_name || "").toLowerCase();
          if (/(programme|program)\s*elective/i.test(name)) return false; // hide placeholders
          if (seen.has(o.course)) return false;
          seen.add(o.course);
          return true;
        });
        setPeOfferings(uniquePe);
        // Pre-fill existing elective_slot_group values and enable state
        const initGroups = {};
        const initEnabled = {};
        allPe.forEach((o) => { initGroups[o.id] = o.elective_slot_group || ""; });
        uniquePe.forEach((o) => { initEnabled[o.id] = true; }); // all ON by default
        setPeSlotGroups(initGroups);
        setPeEnabled(initEnabled);
      } catch {
        setSections([]);
        setPeOfferings([]);
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
    setPeOfferings([]);
    setPeSlotGroups({});
    setPeEnabled({});
  };

  // Save elective_slot_group values to all matching offerings via PATCH
  const savePeSlotGroups = async () => {
    if (!peOfferings.length) return;
    setPeGroupSaving(true);
    try {
      // For each unique PE course, patch all offerings that share the same course
      // Use the course-offerings list endpoint filtered by course to find all sections
      const courseIds = [...new Set(peOfferings.map((o) => o.course))];
      const allOffsResp = await api.get("academics/course-offerings/", {
        params: {
          "student_group__term__program":  selectedProgramId,
          "student_group__term__semester": selectedSemester,
          "course__course_type":           "PE",
        },
      });
      const allOffs = asList(allOffsResp.data);
      // Build a map of course_id → { token, enabled } from the local state
      const courseMap = {};
      peOfferings.forEach((rep) => {
        courseMap[rep.course] = {
          token:   peSlotGroups[rep.id] ?? "",
          enabled: peEnabled[rep.id] !== false,
        };
      });
      // PATCH each non-placeholder offering
      const isPlaceholder = (o) => /(programme|program)\s*elective/i.test(o.course_name || "");
      await Promise.all(
        allOffs
          .filter((o) => !isPlaceholder(o))
          .map((o) => {
            const { token, enabled } = courseMap[o.course] ?? { token: "", enabled: true };
            return api.patch(`academics/course-offerings/${o.id}/`, {
              elective_slot_group: (enabled && token) ? token : null,
            });
          })
      );
    } catch {
      // Non-critical — generation will proceed anyway
    } finally {
      setPeGroupSaving(false);
    }
  };

  // Override generate to save PE groups first
  const handleGenerateWithPE = async () => {
    await savePeSlotGroups();
    handleGenerate();
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

          {/* ── PE Elective Slot Groups ─────────────────────────────────── */}
          {peOfferings.length > 0 && (
            <div style={{
              background: "rgba(168,85,247,0.07)",
              border: "1px solid #a855f7",
              borderRadius: 8, padding: 12, marginBottom: 16,
            }}>
              <p style={{ fontSize: "0.78rem", fontWeight: 700, color: "#a855f7", marginBottom: 6, letterSpacing: 0.5 }}>
                PE ELECTIVE SLOT GROUPS
              </p>
              <p style={{ fontSize: "0.75rem", color: "var(--muted)", marginBottom: 10, lineHeight: 1.4 }}>
                Assign a shared group token to PE courses that must run in parallel (same slot, different rooms).
                Leave blank to schedule each as independent theory.
              </p>
              <div style={{ display: "flex", flexDirection: "column", gap: 8 }}>
                {peOfferings.map((o) => {
                  const on = peEnabled[o.id] !== false;
                  return (
                    <div key={o.id} style={{ display: "flex", alignItems: "center", gap: 8 }}>
                      {/* ON/OFF toggle */}
                      <label style={{ display: "flex", alignItems: "center", gap: 4, flexShrink: 0, cursor: "pointer" }}>
                        <input
                          type="checkbox"
                          checked={on}
                          onChange={(e) =>
                            setPeEnabled((prev) => ({ ...prev, [o.id]: e.target.checked }))
                          }
                          style={{ cursor: "pointer", width: 14, height: 14, accentColor: "#a855f7" }}
                        />
                        <span style={{ fontSize: "0.68rem", fontWeight: 600, color: on ? "#a855f7" : "var(--muted)", minWidth: 22 }}>
                          {on ? "ON" : "OFF"}
                        </span>
                      </label>
                      {/* Course name */}
                      <span style={{
                        flex: 1, fontSize: "0.8rem", fontWeight: 500,
                        overflow: "hidden", textOverflow: "ellipsis", whiteSpace: "nowrap",
                        opacity: on ? 1 : 0.4,
                      }}>
                        {o.course_name || o.course_code || `Course #${o.course}`}
                      </span>
                      {/* Slot group token */}
                      <input
                        className="input"
                        style={{ width: 130, fontSize: "0.8rem", padding: "4px 8px", opacity: on ? 1 : 0.35 }}
                        placeholder="e.g. BCA4-PE1"
                        disabled={!on}
                        value={peSlotGroups[o.id] ?? ""}
                        onChange={(e) =>
                          setPeSlotGroups((prev) => ({ ...prev, [o.id]: e.target.value }))
                        }
                      />
                    </div>
                  );
                })}
              </div>
              <p style={{ fontSize: "0.7rem", color: "var(--muted)", marginTop: 8 }}>
                Toggle OFF to schedule that option independently (not in parallel). All sections inherit the same token.
              </p>
            </div>
          )}

          <button
            type="button"
            className="btn-primary generator-btn"
            onClick={handleGenerateWithPE}
            disabled={!canGenerate || peGroupSaving}
          >
            <FaMagic style={{ marginRight: 6 }} />
            {peGroupSaving
              ? "Saving PE groups..."
              : generating
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
