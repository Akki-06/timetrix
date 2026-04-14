import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import DashboardLayout from "../layouts/DashboardLayout";
import { useAuth } from "../contexts/AuthContext";
import api from "../api/axios";
import { asList } from "../utils/helpers";

const PALETTE = [
  { bg: "rgba(59,130,246,0.12)",  border: "#3b82f6" },
  { bg: "rgba(16,185,129,0.12)",  border: "#10b981" },
  { bg: "rgba(168,85,247,0.12)",  border: "#a855f7" },
  { bg: "rgba(6,182,212,0.12)",   border: "#06b6d4" },
  { bg: "rgba(249,115,22,0.12)",  border: "#f97316" },
  { bg: "rgba(236,72,153,0.12)",  border: "#ec4899" },
  { bg: "rgba(234,179,8,0.12)",   border: "#eab308" },
  { bg: "rgba(99,102,241,0.12)",  border: "#6366f1" },
  { bg: "rgba(244,63,94,0.12)",   border: "#f43f5e" },
  { bg: "rgba(20,184,166,0.12)",  border: "#14b8a6" },
  { bg: "rgba(217,70,239,0.12)",  border: "#d946ef" },
  { bg: "rgba(251,146,60,0.12)",  border: "#fb923c" },
  { bg: "rgba(56,189,248,0.12)",  border: "#38bdf8" },
  { bg: "rgba(52,211,153,0.12)",  border: "#34d399" },
];

const ALL_DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT"];
const DAY_FULL = { MON:"Monday", TUE:"Tuesday", WED:"Wednesday", THU:"Thursday", FRI:"Friday", SAT:"Saturday" };

const VIEW_LABELS = {
  section: "Program / Section",
  faculty: "Faculty Schedule",
  room:    "Room Occupancy",
};

/* ── slot time labels ── */
const SLOT_TIMES = {
  1: "09:40–10:35",
  2: "10:35–11:30",
  3: "11:30–12:25",
  4: "12:25–13:20",
  5: "14:15–15:10",
  6: "15:10–16:05",
};

function GeneratedTimetablesPage() {
  const { user } = useAuth();
  const location = useLocation();
  const role = user?.role || "student";

  const modes =
    role === "admin"   ? ["section", "faculty", "room"] :
    role === "teacher" ? ["faculty", "section"] :
                         ["section"];

  const [viewMode, setViewMode] = useState(modes[0]);

  /* ── reference data ── */
  const [programs, setPrograms]       = useState([]);
  const [terms, setTerms]             = useState([]);
  const [studentGroups, setStudentGroups] = useState([]);
  const [faculties, setFaculties]     = useState([]);
  const [rooms, setRooms]             = useState([]);
  const [buildings, setBuildings]     = useState([]);
  const [timetables, setTimetables]   = useState([]);
  const [timeslots, setTimeslots]     = useState([]);

  /* ── section selectors ── */
  const [selProgram, setSelProgram]     = useState("");
  const [selSemester, setSelSemester]   = useState("");
  const [selSection, setSelSection]     = useState("");
  const [selTimetable, setSelTimetable] = useState("");

  /* ── faculty selector ── */
  const [selFaculty, setSelFaculty]     = useState("");

  /* ── room selectors (building → room) ── */
  const [selBuilding, setSelBuilding]   = useState("");
  const [selRoomType, setSelRoomType]   = useState("");   // THEORY | LAB | ""
  const [selRoom, setSelRoom]           = useState("");

  /* ── data ── */
  const [allocations, setAllocations]   = useState([]);
  const [ttInfo, setTtInfo]             = useState(null);
  const [loading, setLoading]           = useState(true);
  const [schedLoading, setSchedLoading] = useState(false);
  const [error, setError]               = useState("");

  /* ── delete modal ── */
  const [deleteModal, setDeleteModal]   = useState(null);  // { id, label } | null
  const [deleting, setDeleting]         = useState(false);

  const mounted = useRef(false);

  /* ─────────────────── derived selectors ─────────────────── */
  const semesterOptions = useMemo(() => {
    if (!selProgram) return [];
    const prog = programs.find((p) => String(p.id) === selProgram);
    if (!prog) return [];
    const progTerms = terms.filter((t) => t.program === prog.id);
    const sems = [...new Set(progTerms.map((t) => t.semester))].sort((a, b) => a - b);
    return sems.length > 0 ? sems : Array.from({ length: prog.total_semesters }, (_, i) => i + 1);
  }, [selProgram, programs, terms]);

  const sectionOptions = useMemo(() => {
    if (!selProgram || !selSemester) return [];
    const term = terms.find(
      (t) => t.program === Number(selProgram) && t.semester === Number(selSemester),
    );
    if (!term) return [];
    return studentGroups.filter((sg) => sg.term === term.id);
  }, [selProgram, selSemester, terms, studentGroups]);

  const versionOptions = useMemo(() => {
    if (!selProgram || !selSemester) return [];
    const term = terms.find(
      (t) => t.program === Number(selProgram) && t.semester === Number(selSemester),
    );
    if (!term) return [];
    return timetables
      .filter((tt) => tt.term === term.id)
      .sort((a, b) => b.version - a.version);
  }, [selProgram, selSemester, terms, timetables]);

  /* rooms filtered by building + type */
  const filteredRooms = useMemo(() => {
    let rs = rooms;
    if (selBuilding) rs = rs.filter((r) => String(r.building) === selBuilding || String(r.building_id) === selBuilding);
    if (selRoomType) rs = rs.filter((r) => r.room_type === selRoomType);
    return rs.sort((a, b) => a.room_number.localeCompare(b.room_number, undefined, { numeric: true }));
  }, [rooms, selBuilding, selRoomType]);

  /* ─────────────────── load reference data ─────────────────── */
  useEffect(() => {
    mounted.current = false;
    (async () => {
      try {
        setLoading(true);
        const [progR, termR, sgR, facR, roomR, bldR, ttR, tsR] = await Promise.all([
          api.get("academics/programs/"),
          api.get("academics/terms/"),
          api.get("academics/student-groups/"),
          api.get("faculty/faculty/"),
          api.get("infrastructure/room/"),
          api.get("infrastructure/building/"),
          api.get("scheduler/timetables/"),
          api.get("scheduler/timeslots/"),
        ]);

        const progs = asList(progR.data);
        const trms  = asList(termR.data);
        const sgs   = asList(sgR.data);
        const facs  = asList(facR.data).filter((f) => f.is_active !== false);
        const rms   = asList(roomR.data);
        const blds  = asList(bldR.data);
        const tts   = asList(ttR.data);
        const tss   = asList(tsR.data);

        setPrograms(progs);
        setTerms(trms);
        setStudentGroups(sgs);
        setFaculties(facs.sort((a, b) => a.name.localeCompare(b.name)));
        setRooms(rms);
        setBuildings(blds.sort((a, b) => a.name.localeCompare(b.name)));
        setTimetables(tts);
        setTimeslots(tss);

        /* auto-select latest timetable context */
        if (tts.length > 0) {
          const sorted = [...tts].sort((a, b) => new Date(b.created_at) - new Date(a.created_at));
          const latest = sorted[0];
          const term = trms.find((t) => t.id === latest.term);
          if (term) {
            const prog = progs.find((p) => p.id === term.program);
            if (prog) {
              setSelProgram(String(prog.id));
              setSelSemester(String(term.semester));
              const sections = sgs.filter((sg) => sg.term === term.id);
              if (sections.length > 0) setSelSection(String(sections[0].id));
            }
          }
        }
      } catch {
        setError("Failed to load data. Check backend connection.");
      } finally {
        setLoading(false);
        setTimeout(() => { mounted.current = true; }, 0);
      }
    })();
  }, [location.key]); // eslint-disable-line react-hooks/exhaustive-deps

  /* cascade resets */
  useEffect(() => {
    if (!mounted.current) return;
    setSelSemester(""); setSelSection(""); setSelTimetable("");
  }, [selProgram]);
  useEffect(() => {
    if (!mounted.current) return;
    setSelSection(""); setSelTimetable("");
  }, [selSemester]);
  useEffect(() => {
    if (!mounted.current) return;
    setSelRoom("");
  }, [selBuilding, selRoomType]);

  /* ─────────────────── load schedule ─────────────────── */
  const loadSchedule = useCallback(async () => {
    let url = "scheduler/schedule/?";

    if (viewMode === "section") {
      if (!selSection) { setAllocations([]); setTtInfo(null); return; }
      url += `view=section&student_group_id=${selSection}`;
      if (selTimetable) url += `&timetable_id=${selTimetable}`;
    } else if (viewMode === "faculty") {
      if (!selFaculty) { setAllocations([]); setTtInfo(null); return; }
      url += `view=faculty&faculty_id=${selFaculty}`;
    } else if (viewMode === "room") {
      if (!selRoom) { setAllocations([]); setTtInfo(null); return; }
      url += `view=room&room_id=${selRoom}`;
    }

    try {
      setSchedLoading(true);
      const resp = await api.get(url);
      setAllocations(resp.data.allocations || []);
      setTtInfo(resp.data.timetable || null);
    } catch {
      setAllocations([]);
      setTtInfo(null);
    } finally {
      setSchedLoading(false);
    }
  }, [viewMode, selSection, selFaculty, selRoom, selTimetable]);

  useEffect(() => { loadSchedule(); }, [loadSchedule]);

  /* ─────────────────── delete timetable ─────────────────── */
  const confirmDelete = (tt) => {
    setDeleteModal({
      id: tt.id,
      label: `v${tt.version}${tt.is_finalized ? " (Published)" : ""}`,
    });
  };

  const handleDelete = async () => {
    if (!deleteModal) return;
    setDeleting(true);
    try {
      await api.delete(`scheduler/timetables/${deleteModal.id}/`);
      // Remove from local list
      setTimetables((prev) => prev.filter((t) => t.id !== deleteModal.id));
      // If the deleted one was selected, reset selector
      if (String(selTimetable) === String(deleteModal.id)) {
        setSelTimetable("");
      }
      setDeleteModal(null);
    } catch {
      // keep modal open, show nothing — error is transient
    } finally {
      setDeleting(false);
    }
  };

  /* ─────────────────── colour map ─────────────────── */
  const { colorMap, legend } = useMemo(() => {
    const codes = [...new Set(allocations.map((a) => a.course_code))].sort();
    const map = {};
    codes.forEach((code, i) => { map[code] = PALETTE[i % PALETTE.length]; });
    return {
      colorMap: map,
      legend: codes.map((code) => {
        const s = allocations.find((a) => a.course_code === code);
        return { code, name: s?.course_name || code, type: s?.course_type || "", color: map[code] };
      }),
    };
  }, [allocations]);

  /* ─────────────────── active days (respect working_days + SAT) ─────────────────── */
  const activeDays = useMemo(() => {
    const hasSat = allocations.some((a) => a.day === "SAT");
    return hasSat ? ALL_DAYS : ALL_DAYS.slice(0, 5);
  }, [allocations]);

  /* ─────────────────── grid data ─────────────────── */
  const gridData = useMemo(() => {
    const g = {};
    activeDays.forEach((day) => {
      g[day] = {};
      [1, 2, 3, 4, 5, 6].forEach((s) => { g[day][s] = []; });
    });
    allocations.forEach((a) => {
      if (g[a.day]?.[a.slot_number] !== undefined) {
        g[a.day][a.slot_number].push(a);
      }
    });
    return g;
  }, [allocations, activeDays]);

  /* ─────────────────── stats ─────────────────── */
  const stats = useMemo(() => {
    if (!allocations.length) return null;
    const totalSlots = activeDays.length * 6;
    const occupied   = new Set(allocations.map((a) => `${a.day}-${a.slot_number}`)).size;
    const pct        = Math.round((occupied / totalSlots) * 100);

    if (viewMode === "faculty") {
      const courses = [...new Set(allocations.map((a) => a.course_code))];
      return { label: "Weekly Sessions", value: allocations.length, extra: `${courses.length} courses · ${pct}% utilisation` };
    }
    if (viewMode === "room") {
      return { label: "Occupied Slots", value: occupied, extra: `${pct}% utilisation (${totalSlots - occupied} free)` };
    }
    return null;
  }, [allocations, viewMode]);

  /* ─────────────────── banner text ─────────────────── */
  const bannerText = useMemo(() => {
    if (viewMode === "section") {
      const prog = programs.find((p) => String(p.id) === selProgram);
      const sec  = studentGroups.find((sg) => String(sg.id) === selSection);
      if (prog && selSemester && sec) {
        const v = ttInfo ? ` · v${ttInfo.version}${ttInfo.is_finalized ? " (Published)" : ""}` : "";
        return `${prog.code} — Semester ${selSemester} — Section ${sec.name}${v}`;
      }
      return "Select program, semester and section";
    }
    if (viewMode === "faculty") {
      const fac = faculties.find((f) => String(f.id) === selFaculty);
      return fac ? `${fac.name} — Weekly Schedule` : "Select a faculty member";
    }
    if (viewMode === "room") {
      const rm = rooms.find((r) => String(r.id) === selRoom);
      if (rm) {
        const bld = buildings.find((b) => b.id === (rm.building || rm.building_id));
        return `Room ${rm.room_number}${bld ? ` · ${bld.name}` : ""} · ${rm.room_type}`;
      }
      return "Select a room";
    }
    return "";
  }, [viewMode, selProgram, selSemester, selSection, selFaculty, selRoom,
      programs, studentGroups, faculties, rooms, buildings, ttInfo]);

  /* ─────────────────── cell renderers ─────────────────── */

  // Return the short display name for a course (first word or course_code)
  const shortName = (a) => {
    const words = (a.course_name || a.course_code || "").split(" ");
    return words.length > 1 ? words[0] : a.course_code;
  };

  // Render a merged PE chip — all elective options concatenated in one card
  const renderPEChip = (allocations) => {
    const c = { bg: "rgba(168,85,247,0.10)", border: "#a855f7" };
    const line = allocations
      .map((a) => `${shortName(a)} · ${a.building_code}-${a.room_number}`)
      .join(" / ");
    return (
      <div key={`pe-${allocations[0].day}-${allocations[0].slot_number}`}
        className="lecture-chip"
        style={{ background: c.bg, borderLeftColor: c.border }}>
        <div className="lecture-subject" style={{ fontSize: "0.72rem", lineHeight: 1.4 }}>
          <span className="lab-tag" style={{ background: "#a855f7", color: "#fff", marginRight: 4 }}>PE</span>
          {line}
        </div>
        {viewMode === "section" && (
          <div className="lecture-meta" style={{ fontSize: "0.68rem" }}>
            {allocations.map((a) => a.faculty_name).filter(Boolean).join(" / ")}
          </div>
        )}
      </div>
    );
  };

  // Render a single allocation chip (PR lab, PRJ, standard theory)
  const renderChip = (a) => {
    const c = colorMap[a.course_code] || PALETTE[0];
    const isLab      = a.room_type === "LAB" || a.course_type === "PR";
    const isPRJ      = a.course_type === "PRJ";
    const isCombined = a.is_combined;
    // Detect G1/G2 split from section name
    const isG1 = a.student_group_name?.toUpperCase().includes("G1");
    const isG2 = a.student_group_name?.toUpperCase().includes("G2");
    const splitPrefix = isG1 ? "G1 · " : isG2 ? "G2 · " : "";

    return (
      <div key={a.id} className="lecture-chip" style={{ background: c.bg, borderLeftColor: c.border }}>
        <div className="lecture-subject">
          {splitPrefix}{a.course_name}
          {isLab  && <span className="lab-tag">Lab</span>}
          {isPRJ  && <span className="lab-tag" style={{ background: "#0ea5e9", color: "#fff" }}>PRJ</span>}
          {isCombined && <span className="lab-tag" style={{ background: "var(--brand)", color: "#fff" }}>Combined</span>}
        </div>
        {viewMode === "section" && (
          <>
            <div className="lecture-meta">{a.faculty_name}</div>
            <div className="lecture-meta">{a.building_code}-{a.room_number}</div>
          </>
        )}
        {viewMode === "faculty" && (
          <>
            <div className="lecture-meta">{a.program_code} · Sec {a.student_group_name}</div>
            <div className="lecture-meta">{a.building_code}-{a.room_number}</div>
          </>
        )}
        {viewMode === "room" && (
          <>
            <div className="lecture-meta">{a.program_code} · Sec {a.student_group_name}</div>
            <div className="lecture-meta">{a.faculty_name}</div>
          </>
        )}
      </div>
    );
  };

  // Render all allocations in a cell — merge PE options into one card
  const renderCell = (cells) => {
    if (!cells.length) return null;
    const peItems    = cells.filter((a) => a.course_type === "PE");
    const nonPeItems = cells.filter((a) => a.course_type !== "PE");
    return (
      <>
        {peItems.length > 0 && renderPEChip(peItems)}
        {nonPeItems.map(renderChip)}
      </>
    );
  };

  /* ─────────────────── render ─────────────────── */
  if (loading) {
    return (
      <DashboardLayout>
        <div className="page-head"><h1>Timetables</h1><p>Loading...</p></div>
      </DashboardLayout>
    );
  }

  if (error) {
    return (
      <DashboardLayout>
        <div className="page-head"><h1>Timetables</h1><p style={{ color: "var(--danger)" }}>{error}</p></div>
      </DashboardLayout>
    );
  }

  const hasData = allocations.length > 0;

  return (
    <DashboardLayout>
      <div className="page-head no-print">
        <h1>Timetables</h1>
        <p>View class schedules, faculty workload, and room occupancy.</p>
      </div>

      {/* View mode tabs */}
      {modes.length > 1 && (
        <div className="pill-tabs no-print" style={{ marginBottom: 16 }}>
          {modes.map((m) => (
            <button key={m} type="button" className={viewMode === m ? "active" : ""}
              onClick={() => setViewMode(m)}>
              {VIEW_LABELS[m]}
            </button>
          ))}
        </div>
      )}

      {/* ── Filters card ── */}
      <section className="data-card no-print" style={{ marginBottom: 16 }}>
        <div className="manual-form">

          {/* SECTION selectors */}
          {viewMode === "section" && (
            <>
              <div className="form-group">
                <label className="form-label">Program</label>
                <select className="input" value={selProgram} onChange={(e) => setSelProgram(e.target.value)}>
                  <option value="">Select Program</option>
                  {programs.map((p) => (
                    <option key={p.id} value={p.id}>{p.code} — {p.name}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Semester</label>
                <select className="input" value={selSemester}
                  onChange={(e) => setSelSemester(e.target.value)} disabled={!selProgram}>
                  <option value="">Select Semester</option>
                  {semesterOptions.map((s) => (
                    <option key={s} value={s}>Semester {s}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Section</label>
                <select className="input" value={selSection}
                  onChange={(e) => setSelSection(e.target.value)} disabled={!sectionOptions.length}>
                  <option value="">Select Section</option>
                  {sectionOptions.map((sg) => (
                    <option key={sg.id} value={sg.id}>{sg.name} (Strength: {sg.strength})</option>
                  ))}
                </select>
              </div>
              {role === "admin" && versionOptions.length > 0 && (
                <div className="form-group">
                  <label className="form-label">Version</label>
                  <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
                    <select className="input" value={selTimetable} onChange={(e) => setSelTimetable(e.target.value)}>
                      <option value="">Latest</option>
                      {versionOptions.map((tt) => (
                        <option key={tt.id} value={tt.id}>v{tt.version}{tt.is_finalized ? " (Published)" : ""}</option>
                      ))}
                    </select>
                    {/* Delete the currently-selected version (or latest if none selected) */}
                    {(() => {
                      const ttToDel = selTimetable
                        ? versionOptions.find((t) => String(t.id) === selTimetable)
                        : versionOptions[0];
                      if (!ttToDel) return null;
                      return (
                        <button
                          type="button"
                          title={`Delete timetable v${ttToDel.version}`}
                          onClick={() => confirmDelete(ttToDel)}
                          style={{
                            background: "transparent",
                            border: "1px solid var(--danger, #ef4444)",
                            color: "var(--danger, #ef4444)",
                            borderRadius: "var(--radius)",
                            padding: "6px 10px",
                            cursor: "pointer",
                            fontSize: 16,
                            lineHeight: 1,
                            flexShrink: 0,
                          }}
                        >
                          🗑
                        </button>
                      );
                    })()}
                  </div>
                </div>
              )}
            </>
          )}

          {/* FACULTY selector */}
          {viewMode === "faculty" && (
            <div className="form-group" style={{ minWidth: 300 }}>
              <label className="form-label">Faculty Member</label>
              <select className="input" value={selFaculty} onChange={(e) => setSelFaculty(e.target.value)}>
                <option value="">Select Faculty</option>
                {faculties.map((f) => (
                  <option key={f.id} value={f.id}>{f.name}{f.department ? ` · ${f.department}` : ""}</option>
                ))}
              </select>
            </div>
          )}

          {/* ROOM selectors: Building → Type → Room */}
          {viewMode === "room" && (
            <>
              <div className="form-group">
                <label className="form-label">Building</label>
                <select className="input" value={selBuilding} onChange={(e) => setSelBuilding(e.target.value)}>
                  <option value="">All Buildings</option>
                  {buildings.map((b) => (
                    <option key={b.id} value={b.id}>{b.name}{b.code ? ` (${b.code})` : ""}</option>
                  ))}
                </select>
              </div>
              <div className="form-group">
                <label className="form-label">Room Type</label>
                <select className="input" value={selRoomType} onChange={(e) => setSelRoomType(e.target.value)}>
                  <option value="">All Types</option>
                  <option value="THEORY">Theory</option>
                  <option value="LAB">Lab</option>
                </select>
              </div>
              <div className="form-group" style={{ minWidth: 200 }}>
                <label className="form-label">Room</label>
                <select className="input" value={selRoom} onChange={(e) => setSelRoom(e.target.value)}
                  disabled={!filteredRooms.length}>
                  <option value="">Select Room</option>
                  {filteredRooms.map((r) => (
                    <option key={r.id} value={r.id}>
                      {r.room_number} · {r.room_type} · Cap {r.capacity}
                    </option>
                  ))}
                </select>
              </div>
            </>
          )}
        </div>
      </section>

      {/* ── Stats bar (faculty / room only) ── */}
      {hasData && stats && (
        <div className="no-print" style={{
          display: "flex", gap: 12, marginBottom: 16,
        }}>
          <div style={{
            background: "var(--brand-light)", border: "1px solid var(--stroke)",
            borderRadius: "var(--radius)", padding: "12px 20px",
            display: "flex", alignItems: "center", gap: 16,
          }}>
            <div>
              <div style={{ fontSize: 11, color: "var(--muted)", textTransform: "uppercase", letterSpacing: 1 }}>
                {stats.label}
              </div>
              <div style={{ fontSize: 24, fontWeight: 700, color: "var(--brand)" }}>{stats.value}</div>
            </div>
            <div style={{ fontSize: 13, color: "var(--text-secondary)" }}>{stats.extra}</div>
          </div>
        </div>
      )}

      {/* ── Timetable grid ── */}
      <section className="timetable-card">
        <div className="timetable-top no-print">
          <div className="view-banner" style={{ flex: 1 }}>
            {bannerText}
            {schedLoading && " — Loading..."}
          </div>
          {hasData && (
            <button type="button" className="btn-primary" onClick={() => window.print()}>
              Download PDF
            </button>
          )}
        </div>

        {schedLoading ? (
          <div style={{ padding: "3rem", textAlign: "center", color: "var(--muted)" }}>
            Loading schedule...
          </div>
        ) : !hasData ? (
          <div style={{ padding: "3rem", textAlign: "center", color: "var(--muted)" }}>
            {timetables.length === 0
              ? "No timetables generated yet. Use the Generator page."
              : (viewMode === "section" && selSection) ||
                (viewMode === "faculty" && selFaculty) ||
                (viewMode === "room" && selRoom)
                ? "No allocations found. Generate a timetable first."
                : "Select filters above to view a timetable."}
          </div>
        ) : (
          <div className="timetable-grid-wrap">
            <table className="timetable-grid">
              <thead>
                <tr>
                  <th className="day-label-col">Day</th>
                  {[1, 2, 3, 4].map((s) => (
                    <th key={s}><span className="slot-num">S{s}</span><br /><span className="slot-time">{SLOT_TIMES[s]}</span></th>
                  ))}
                  <th className="lunch-col">LUNCH<br /><span className="slot-time">13:20–14:15</span></th>
                  {[5, 6].map((s) => (
                    <th key={s}><span className="slot-num">S{s}</span><br /><span className="slot-time">{SLOT_TIMES[s]}</span></th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {activeDays.map((day) => (
                  <tr key={day}>
                    <td className="day-label">{DAY_FULL[day]}</td>
                    {[1, 2, 3, 4].map((slot) => {
                      const cells = gridData[day]?.[slot] || [];
                      return (
                        <td key={slot} className={cells.length ? "has-class" : "empty-cell"}>
                          {renderCell(cells)}
                        </td>
                      );
                    })}
                    <td className="lunch-col lunch-cell">LUNCH</td>
                    {[5, 6].map((slot) => {
                      const cells = gridData[day]?.[slot] || [];
                      return (
                        <td key={slot} className={cells.length ? "has-class" : "empty-cell"}>
                          {renderCell(cells)}
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {hasData && (
          <div className="legend-row no-print">
            {legend.map((item) => (
              <div key={item.code} className="legend-item">
                <span className="legend-box" style={{
                  background: item.type === "PE"  ? "#a855f7"
                            : item.type === "PRJ" ? "#0ea5e9"
                            : item.color.border
                }} />
                {item.name}
                {item.type === "PR"  && " (Lab)"}
                {item.type === "PRJ" && " (Project)"}
                {item.type === "PE"  && " (Elective)"}
              </div>
            ))}
          </div>
        )}
      </section>
      {/* ── Delete confirmation modal ── */}
      {deleteModal && (
        <div style={{
          position: "fixed", inset: 0, zIndex: 1000,
          background: "rgba(0,0,0,0.45)",
          display: "flex", alignItems: "center", justifyContent: "center",
        }}>
          <div style={{
            background: "var(--surface, #fff)",
            border: "1px solid var(--stroke, #e5e7eb)",
            borderRadius: "var(--radius, 8px)",
            padding: "28px 32px",
            maxWidth: 420, width: "90%",
            boxShadow: "0 8px 32px rgba(0,0,0,0.18)",
          }}>
            <h3 style={{ margin: "0 0 8px", fontSize: 18, fontWeight: 700, color: "var(--text)" }}>
              Delete Timetable?
            </h3>
            <p style={{ margin: "0 0 20px", color: "var(--text-secondary)", fontSize: 14, lineHeight: 1.5 }}>
              You are about to permanently delete timetable{" "}
              <strong>{deleteModal.label}</strong>. This will remove all{" "}
              lecture allocations in this version and cannot be undone.
            </p>
            <div style={{ display: "flex", gap: 10, justifyContent: "flex-end" }}>
              <button
                type="button"
                onClick={() => setDeleteModal(null)}
                disabled={deleting}
                style={{
                  padding: "8px 18px", borderRadius: "var(--radius)",
                  border: "1px solid var(--stroke)", background: "transparent",
                  cursor: "pointer", fontSize: 14, color: "var(--text)",
                }}
              >
                Cancel
              </button>
              <button
                type="button"
                onClick={handleDelete}
                disabled={deleting}
                style={{
                  padding: "8px 18px", borderRadius: "var(--radius)",
                  border: "none", background: "var(--danger, #ef4444)",
                  color: "#fff", cursor: deleting ? "not-allowed" : "pointer",
                  fontSize: 14, fontWeight: 600, opacity: deleting ? 0.7 : 1,
                }}
              >
                {deleting ? "Deleting…" : "Delete"}
              </button>
            </div>
          </div>
        </div>
      )}
    </DashboardLayout>
  );
}

export default GeneratedTimetablesPage;
