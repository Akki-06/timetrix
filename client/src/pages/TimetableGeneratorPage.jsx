import { useCallback, useEffect, useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import { asList, extractError } from "../utils/helpers";
import {
  FaMagic, FaUsers, FaCheckCircle, FaExclamationTriangle,
  FaArrowRight, FaRocket, FaHistory, FaClock, FaChartBar,
  FaBrain, FaLayerGroup, FaTimes, FaCalendarCheck,
} from "react-icons/fa";

function yearFromSemester(sem) {
  return Math.ceil(sem / 2);
}

function timeAgo(dateStr) {
  if (!dateStr) return "—";
  const diff = Math.floor((Date.now() - new Date(dateStr)) / 1000);
  if (diff < 60) return "just now";
  if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
  if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
  return `${Math.floor(diff / 86400)}d ago`;
}

function ScorePill({ score }) {
  if (score == null) return <span className="gen-score-pill gen-score-na">—</span>;
  const n = Number(score);
  const cls = n >= 0.95 ? "gen-score-great" : n >= 0.8 ? "gen-score-ok" : "gen-score-low";
  return <span className={`gen-score-pill ${cls}`}>{n.toFixed(3)}</span>;
}

function TimetableGeneratorPage() {
  const navigate = useNavigate();

  const [programs,  setPrograms]  = useState([]);
  const [timetables, setTimetables] = useState([]);
  const [sections,  setSections]  = useState([]);

  const [selectedProgramId, setSelectedProgramId] = useState("");
  const [selectedSemester,  setSelectedSemester]  = useState("");

  const [pageLoading,     setPageLoading]     = useState(true);
  const [sectionsLoading, setSectionsLoading] = useState(false);
  const [generating,      setGenerating]      = useState(false);
  const [result,          setResult]          = useState(null);
  const [error,           setError]           = useState("");

  // PE state
  const [peOfferings,   setPeOfferings]   = useState([]);
  const [peSlotGroups,  setPeSlotGroups]  = useState({});
  const [peEnabled,     setPeEnabled]     = useState({});
  const [peGroupSaving, setPeGroupSaving] = useState(false);

  // animation tick for the generate button
  const [genTick, setGenTick] = useState(0);

  /* ── load ── */
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

  /* ── sections + PE when program/semester changes ── */
  useEffect(() => {
    if (!selectedProgramId || !selectedSemester) {
      setSections([]); setPeOfferings([]); setPeSlotGroups({}); setPeEnabled({});
      return;
    }
    const load = async () => {
      setSectionsLoading(true);
      try {
        const [sgResp, peResp] = await Promise.all([
          api.get("academics/student-groups/", {
            params: { "term__program": selectedProgramId, "term__semester": selectedSemester },
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

        const allPe = asList(peResp.data);
        const seen  = new Set();
        const uniquePe = allPe.filter((o) => {
          if (/(programme|program)\s*elective/i.test(o.course_name || "")) return false;
          if (seen.has(o.course)) return false;
          seen.add(o.course);
          return true;
        });
        setPeOfferings(uniquePe);
        const initGroups = {}; const initEnabled = {};
        allPe.forEach((o)    => { initGroups[o.id]  = o.elective_slot_group || ""; });
        uniquePe.forEach((o) => { initEnabled[o.id] = true; });
        setPeSlotGroups(initGroups);
        setPeEnabled(initEnabled);
      } catch {
        setSections([]); setPeOfferings([]);
      } finally {
        setSectionsLoading(false);
      }
    };
    load();
  }, [selectedProgramId, selectedSemester]);

  const selectedProgram   = useMemo(() => programs.find((p) => String(p.id) === String(selectedProgramId)) || null, [programs, selectedProgramId]);
  const semesterOptions   = useMemo(() => selectedProgram ? Array.from({ length: selectedProgram.total_semesters || 8 }, (_, i) => i + 1) : [], [selectedProgram]);
  const programMap        = useMemo(() => Object.fromEntries(programs.map((p) => [p.id, p])), [programs]);
  const canGenerate       = selectedProgramId && selectedSemester && sections.length > 0 && !generating;
  const derivedYear       = selectedSemester ? yearFromSemester(Number(selectedSemester)) : null;

  /* ── generate ── */
  const handleGenerate = async () => {
    if (!selectedProgramId || !selectedSemester || sections.length === 0) return;
    setGenerating(true); setError(""); setResult(null);
    const tick = setInterval(() => setGenTick(t => t + 1), 400);
    try {
      const resp = await api.post("scheduler/generate/", {
        program_id: Number(selectedProgramId),
        semester:   Number(selectedSemester),
      }, { timeout: 120000 });
      setResult(resp.data);
      const ttResp = await api.get("scheduler/timetables/", { params: { ordering: "-created_at" } });
      setTimetables(asList(ttResp.data));
      if (resp.data.allocations > 0) setTimeout(() => navigate("/generated"), 2500);
    } catch (err) {
      const errData = err?.response?.data;
      if (errData?.status) setResult(errData);
      else setError(extractError(err, "Generation failed. Check server logs."));
      try {
        const ttResp = await api.get("scheduler/timetables/", { params: { ordering: "-created_at" } });
        setTimetables(asList(ttResp.data));
      } catch { /* ignore */ }
    } finally {
      clearInterval(tick);
      setGenerating(false);
    }
  };

  const handleProgramChange = (val) => {
    setSelectedProgramId(val); setSelectedSemester("");
    setResult(null); setError(""); setSections([]);
    setPeOfferings([]); setPeSlotGroups({}); setPeEnabled({});
  };

  const savePeSlotGroups = async () => {
    if (!peOfferings.length) return;
    setPeGroupSaving(true);
    try {
      const allOffsResp = await api.get("academics/course-offerings/", {
        params: {
          "student_group__term__program":  selectedProgramId,
          "student_group__term__semester": selectedSemester,
          "course__course_type":           "PE",
        },
      });
      const allOffs = asList(allOffsResp.data);
      const courseMap = {};
      peOfferings.forEach((rep) => {
        courseMap[rep.course] = {
          token:   peSlotGroups[rep.id] ?? "",
          enabled: peEnabled[rep.id] !== false,
        };
      });
      const isPlaceholder = (o) => /(programme|program)\s*elective/i.test(o.course_name || "");
      await Promise.all(
        allOffs.filter((o) => !isPlaceholder(o)).map((o) => {
          const { token, enabled } = courseMap[o.course] ?? { token: "", enabled: true };
          return api.patch(`academics/course-offerings/${o.id}/`, {
            elective_slot_group: (enabled && token) ? token : null,
          });
        })
      );
    } catch { /* non-critical */ } finally { setPeGroupSaving(false); }
  };

  const handleGenerateWithPE = async () => {
    await savePeSlotGroups();
    handleGenerate();
  };

  /* ── loading state ── */
  if (pageLoading) {
    return (
      <DashboardLayout>
        <div className="sec-loading" style={{ minHeight: 300 }}>
          <div className="sec-loading-spinner" />
          Loading generator…
        </div>
      </DashboardLayout>
    );
  }

  const dots = ".".repeat((genTick % 3) + 1);

  return (
    <DashboardLayout>

      {/* ── Header ── */}
      <div className="sec-page-header">
        <div>
          <h1 className="sec-page-title">Timetable Generator</h1>
          <p className="sec-page-sub">
            Select a program and semester — AI assigns rooms, slots, and faculty for every section automatically.
          </p>
        </div>
        {result && result.allocations > 0 && (
          <button className="sec-add-btn" onClick={() => navigate("/generated")}>
            <FaCalendarCheck /> View Timetable
          </button>
        )}
      </div>

      {/* ── Global alert ── */}
      {error && <div className="sec-alert sec-alert-error">{error}</div>}

      <div className="gen-layout">

        {/* ════ LEFT COLUMN ════ */}
        <div className="gen-left">

          {/* ── Config card ── */}
          <div className="gen-config-card">
            <div className="gen-card-header">
              <div className="gen-card-icon" style={{ background: "rgba(99,102,241,0.12)", color: "var(--brand)" }}>
                <FaBrain />
              </div>
              <div>
                <h3 className="gen-card-title">Generation Parameters</h3>
                <p className="gen-card-sub">Choose the program and semester to schedule</p>
              </div>
            </div>

            {/* Program */}
            <div className="gen-fields-grid">
              <div className="sec-field">
                <label>Program <span className="sec-req">*</span></label>
                <select value={selectedProgramId} onChange={(e) => handleProgramChange(e.target.value)}>
                  <option value="">Select program</option>
                  {[...programs].sort((a, b) => (a.display_name || a.name || "").localeCompare(b.display_name || b.name || "")).map((p) => (
                    <option key={p.id} value={p.id}>{p.display_name || p.name} ({p.code})</option>
                  ))}
                </select>
              </div>

              <div className="sec-field">
                <label>Semester <span className="sec-req">*</span></label>
                <select value={selectedSemester}
                  onChange={(e) => { setSelectedSemester(e.target.value); setResult(null); setError(""); }}
                  disabled={!selectedProgramId}>
                  <option value="">{selectedProgramId ? "Select semester" : "Select program first"}</option>
                  {semesterOptions.map((s) => (
                    <option key={s} value={s}>Semester {s} — Year {yearFromSemester(s)}</option>
                  ))}
                </select>
              </div>
            </div>

            {/* Year info badge */}
            {selectedSemester && (
              <div className="gen-info-badge">
                <FaCalendarCheck style={{ color: "var(--brand)" }} />
                <span>
                  <strong>Year {derivedYear}</strong> of {selectedProgram?.display_name || selectedProgram?.name}
                </span>
              </div>
            )}

            {/* Sections preview */}
            {selectedProgramId && selectedSemester && (
              <div className="gen-sections-box">
                <p className="gen-sections-label">
                  <FaUsers /> Sections to be Scheduled
                </p>
                {sectionsLoading ? (
                  <div className="sec-loading" style={{ padding: "16px 0", justifyContent: "flex-start" }}>
                    <div className="sec-loading-spinner" style={{ width: 18, height: 18 }} />
                    <span>Loading sections…</span>
                  </div>
                ) : sections.length === 0 ? (
                  <p className="gen-sections-empty">
                    No sections found for {selectedProgram?.display_name} Sem {selectedSemester}.{" "}
                    <a href="/sections">Register sections first →</a>
                  </p>
                ) : (
                  <>
                    <p className="gen-sections-count">
                      {sections.length} section{sections.length > 1 ? "s" : ""} — all will be scheduled
                    </p>
                    <div className="gen-section-chips">
                      {sections.map((s) => (
                        <div key={s.id} className="gen-section-chip">
                          <FaUsers style={{ fontSize: 10, color: "var(--brand)" }} />
                          <strong>{s.name}</strong>
                          <span className="gen-chip-strength">{s.strength} students</span>
                        </div>
                      ))}
                    </div>
                  </>
                )}
              </div>
            )}

            {/* PE Elective Slot Groups */}
            {peOfferings.length > 0 && (
              <div className="gen-pe-box">
                <div className="gen-pe-header">
                  <FaLayerGroup />
                  <span>PE Elective Slot Groups</span>
                </div>
                <p className="gen-pe-hint">
                  Assign a shared group token to PE courses that must run in parallel (same slot, different rooms). Leave blank to schedule independently.
                </p>
                <div className="gen-pe-list">
                  {peOfferings.map((o) => {
                    const on = peEnabled[o.id] !== false;
                    return (
                      <div key={o.id} className="gen-pe-row">
                        <label className="gen-pe-toggle">
                          <input type="checkbox" checked={on}
                            onChange={(e) => setPeEnabled((p) => ({ ...p, [o.id]: e.target.checked }))}
                            style={{ accentColor: "#a855f7" }}
                          />
                          <span style={{ color: on ? "#a855f7" : "var(--muted)", fontWeight: 700, fontSize: 11 }}>
                            {on ? "ON" : "OFF"}
                          </span>
                        </label>
                        <span className="gen-pe-name" style={{ opacity: on ? 1 : 0.4 }}>
                          {o.course_name || o.course_code || `Course #${o.course}`}
                        </span>
                        <input
                          className="gen-pe-input"
                          placeholder="e.g. BCA4-PE1"
                          disabled={!on}
                          value={peSlotGroups[o.id] ?? ""}
                          onChange={(e) => setPeSlotGroups((p) => ({ ...p, [o.id]: e.target.value }))}
                          style={{ opacity: on ? 1 : 0.35 }}
                        />
                      </div>
                    );
                  })}
                </div>
                <p className="gen-pe-note">Toggle OFF to schedule that option independently. All sections inherit the same token.</p>
              </div>
            )}

            {/* Generate button */}
            <button
              className="gen-generate-btn"
              onClick={handleGenerateWithPE}
              disabled={!canGenerate || peGroupSaving}
            >
              {generating ? (
                <>
                  <span className="gen-btn-spinner" />
                  Scheduling {sections.length} section{sections.length > 1 ? "s" : ""}{dots}
                </>
              ) : peGroupSaving ? (
                <><FaLayerGroup /> Saving PE groups…</>
              ) : (
                <><FaRocket /> Generate Timetable</>
              )}
            </button>
          </div>

          {/* ── Result card ── */}
          {result && (
            <div className={`gen-result-card gen-result-${result.status || "error"}`}>
              <div className="gen-result-header">
                <div className="gen-result-icon">
                  {result.status === "success" ? <FaCheckCircle /> : <FaExclamationTriangle />}
                </div>
                <div>
                  <h3 className="gen-result-title">
                    {result.status === "success" ? "Fully Scheduled" :
                     result.status === "partial"  ? "Partially Scheduled" :
                     `Generation Failed`}
                  </h3>
                  {result.reason && <p className="gen-result-reason">{result.reason}</p>}
                </div>
              </div>

              <div className="gen-result-stats">
                <div className="gen-result-stat">
                  <span className="gen-result-stat-val">{result.allocations ?? 0}</span>
                  <span className="gen-result-stat-lbl">Allocations</span>
                </div>
                <div className="gen-result-stat">
                  <ScorePill score={result.avg_score} />
                  <span className="gen-result-stat-lbl">Avg Score</span>
                </div>
                <div className="gen-result-stat">
                  <span className="gen-result-stat-val" style={{ color: result.ml_used ? "var(--success)" : "var(--muted)" }}>
                    {result.ml_used ? "Yes" : "No"}
                  </span>
                  <span className="gen-result-stat-lbl">ML Used</span>
                </div>
              </div>

              {(result.allocations ?? 0) > 0 && (
                <button className="gen-view-btn" onClick={() => navigate("/generated")}>
                  <FaArrowRight /> View Generated Timetable
                </button>
              )}

              {/* Per-section breakdown */}
              {Array.isArray(result.sections) && result.sections.length > 0 && (
                <div className="gen-section-table">
                  <p className="gen-section-table-title">Per-Section Result</p>
                  <div className="table-wrap">
                    <table>
                      <thead>
                        <tr>
                          <th>Section</th>
                          <th>Strength</th>
                          <th>Scheduled</th>
                        </tr>
                      </thead>
                      <tbody>
                        {result.sections.map((s) => (
                          <tr key={s.section}>
                            <td><strong>Section {s.section}</strong></td>
                            <td>{s.strength}</td>
                            <td>
                              <span style={{ color: s.allocated > 0 ? "var(--success)" : "var(--danger)", fontWeight: 600 }}>
                                {s.allocated} sessions
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

          {/* ── Unscheduled items ── */}
          {result && Array.isArray(result.unscheduled) && result.unscheduled.length > 0 && (
            <div className="gen-unscheduled-card">
              <div className="gen-card-header">
                <div className="gen-card-icon" style={{ background: "rgba(239,68,68,0.1)", color: "var(--danger)" }}>
                  <FaTimes />
                </div>
                <div>
                  <h3 className="gen-card-title">Unscheduled Items ({result.unscheduled.length})</h3>
                  <p className="gen-card-sub">Could not be placed due to conflicts</p>
                </div>
              </div>
              <ul className="gen-unscheduled-list">
                {result.unscheduled.map((item, i) => (
                  <li key={i} className="gen-unscheduled-item">{item}</li>
                ))}
              </ul>
            </div>
          )}
        </div>

        {/* ════ RIGHT COLUMN: History ════ */}
        <div className="gen-right">
          <div className="gen-history-card">
            <div className="gen-card-header">
              <div className="gen-card-icon" style={{ background: "rgba(20,184,166,0.1)", color: "var(--accent)" }}>
                <FaHistory />
              </div>
              <div>
                <h3 className="gen-card-title">Generation History</h3>
                <p className="gen-card-sub">{timetables.length} version{timetables.length !== 1 ? "s" : ""} generated</p>
              </div>
            </div>

            {timetables.length === 0 ? (
              <div className="sec-empty" style={{ padding: "40px 16px" }}>
                <FaHistory className="sec-empty-icon" />
                <h3>No history yet</h3>
                <p>Generate your first timetable to see it here.</p>
              </div>
            ) : (
              <div className="gen-history-list">
                {timetables.map((tt, i) => {
                  const createdAt = tt.created_at ? new Date(tt.created_at) : null;
                  const isLatest  = i === 0;
                  const score     = tt.total_constraint_score;
                  return (
                    <div key={tt.id} className={`gen-history-item${isLatest ? " gen-history-latest" : ""}`}>
                      <div className="gen-history-left">
                        <div className="gen-history-icon">
                          <FaCalendarCheck />
                        </div>
                        <div className="gen-history-info">
                          <div className="gen-history-name">
                            {tt.program_code
                              ? `${tt.program_code} Sem ${tt.semester}`
                              : tt.program_name
                              ? `${tt.program_name} Sem ${tt.semester}`
                              : `Term #${tt.term}`}
                            <span className="gen-history-version">v{tt.version}</span>
                            {tt.is_finalized && (
                              <span className="gen-history-final">FINAL</span>
                            )}
                            {isLatest && (
                              <span className="gen-history-latest-badge">Latest</span>
                            )}
                          </div>
                          <div className="gen-history-meta">
                            <FaClock style={{ fontSize: 10 }} />
                            <span>{createdAt ? createdAt.toLocaleDateString("en-IN", { day: "2-digit", month: "short", year: "numeric" }) : "—"}</span>
                            <span style={{ color: "var(--muted)" }}>·</span>
                            <span>{timeAgo(tt.created_at)}</span>
                          </div>
                        </div>
                      </div>
                      <div className="gen-history-right">
                        <ScorePill score={score} />
                        <button className="gen-history-view-btn" onClick={() => navigate("/generated")}>
                          <FaArrowRight />
                        </button>
                      </div>
                    </div>
                  );
                })}
              </div>
            )}
          </div>

          {/* ── Quick Stats strip ── */}
          {timetables.length > 0 && (
            <div className="gen-quick-stats">
              <div className="gen-quick-stat">
                <FaChartBar style={{ color: "var(--brand)" }} />
                <div>
                  <span className="gen-qs-val">{timetables.length}</span>
                  <span className="gen-qs-lbl">Total Runs</span>
                </div>
              </div>
              <div className="gen-quick-stat">
                <FaCheckCircle style={{ color: "var(--success)" }} />
                <div>
                  <span className="gen-qs-val">{timetables.filter(t => t.is_finalized).length}</span>
                  <span className="gen-qs-lbl">Finalized</span>
                </div>
              </div>
              <div className="gen-quick-stat">
                <FaBrain style={{ color: "var(--accent)" }} />
                <div>
                  <span className="gen-qs-val">
                    {timetables.length > 0
                      ? Number(timetables[0].total_constraint_score ?? 0).toFixed(2)
                      : "—"}
                  </span>
                  <span className="gen-qs-lbl">Latest Score</span>
                </div>
              </div>
            </div>
          )}
        </div>

      </div>
    </DashboardLayout>
  );
}

export default TimetableGeneratorPage;
