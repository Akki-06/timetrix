import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useNavigate, useParams } from "react-router-dom";
import api from "../api/axios";
import { asList } from "../utils/helpers";
import "../styles/timetable-editor.css";

/* ─── constants ─────────────────────────────────────────────── */

const PALETTE = [
  { bg: "rgba(99,102,241,0.14)",  border: "#6366f1", solid: "#6366f1" },
  { bg: "rgba(16,185,129,0.14)",  border: "#10b981", solid: "#10b981" },
  { bg: "rgba(249,115,22,0.14)",  border: "#f97316", solid: "#f97316" },
  { bg: "rgba(168,85,247,0.14)",  border: "#a855f7", solid: "#a855f7" },
  { bg: "rgba(236,72,153,0.14)",  border: "#ec4899", solid: "#ec4899" },
  { bg: "rgba(6,182,212,0.14)",   border: "#06b6d4", solid: "#06b6d4" },
  { bg: "rgba(234,179,8,0.14)",   border: "#eab308", solid: "#eab308" },
  { bg: "rgba(244,63,94,0.14)",   border: "#f43f5e", solid: "#f43f5e" },
  { bg: "rgba(20,184,166,0.14)",  border: "#14b8a6", solid: "#14b8a6" },
  { bg: "rgba(217,70,239,0.14)",  border: "#d946ef", solid: "#d946ef" },
  { bg: "rgba(56,189,248,0.14)",  border: "#38bdf8", solid: "#38bdf8" },
  { bg: "rgba(251,146,60,0.14)",  border: "#fb923c", solid: "#fb923c" },
  { bg: "rgba(52,211,153,0.14)",  border: "#34d399", solid: "#34d399" },
  { bg: "rgba(59,130,246,0.14)",  border: "#3b82f6", solid: "#3b82f6" },
];

const ALL_DAYS = ["MON", "TUE", "WED", "THU", "FRI", "SAT"];
const DAY_FULL = { MON: "Monday", TUE: "Tuesday", WED: "Wednesday", THU: "Thursday", FRI: "Friday", SAT: "Saturday" };
const SLOT_TIMES = {
  1: "09:40–10:35", 2: "10:35–11:30", 3: "11:30–12:25",
  4: "12:25–13:20", 5: "14:15–15:10", 6: "15:10–16:05",
};
// (slot, slot+1) lab pairs — lunch breaks the (4,5) chain
const LAB_PAIRS = new Set(["1-2", "2-3", "3-4", "5-6"]);

/* (Note: HTML5 drag was abandoned in favor of pointer-based drag — Chrome
   on Windows insisted on rendering a viewport-sized "white ghost" no matter
   how we tried to override setDragImage. Pointer events give us full
   control: a floating React-rendered preview follows the cursor.) */

/* ─── helpers ─────────────────────────────────────────────── */

const cellKey   = (day, slot) => `${day}-${slot}`;
const isLabPair = (slot)      => LAB_PAIRS.has(`${slot}-${slot + 1}`);

const colorFor = (code, map) => map[code] || PALETTE[0];

/* ─── normalise an alloc from the server response ─── */
const normaliseAlloc = (a) => ({
  id:                  a.id,
  day:                 a.day,
  slot:                a.slot_number,
  course_offering_id:  a.course_offering_id,
  faculty_id:          a.faculty_id,
  room_id:             a.room_id,
  course_code:         a.course_code,
  course_name:         a.course_name,
  course_type:         a.course_type,
  faculty_name:        a.faculty_name,
  room_number:         a.room_number,
  building_code:       a.building_code,
  room_type:           a.room_type,
  student_group_name:  a.student_group_name,
  student_group_id:    a.student_group_id,
  is_combined:         a.is_combined,
  elective_slot_group: a.elective_slot_group,
  combined_token:      a.combined_token,
  is_lab:              a.is_lab,
  is_pe:               a.is_pe,
  requires_consecutive: a.requires_consecutive,
  status:              a.status || "ok",
});

function TimetableEditorPage() {
  const { timetableId, sectionId } = useParams();
  const navigate = useNavigate();
  /* refs to track unsaved changes for the exit-confirm modal */
  const initialAllocsRef = useRef(null);

  /* ─── data ─── */
  const [loading,    setLoading]    = useState(true);
  const [error,      setError]      = useState("");
  const [timetable,  setTimetable]  = useState(null);   // {id, version, term}
  const [section,    setSection]    = useState(null);
  const [offerings,  setOfferings]  = useState([]);     // palette items
  const [faculties,  setFaculties]  = useState([]);

  /* draft timetable (copy-on-edit) */
  const [draftId,    setDraftId]    = useState(null);

  /* working grid: array of allocation rows
     row = {id, day, slot, course_offering_id, faculty_id, room_id, course_code, course_name, course_type, faculty_name, room_number, building_code, room_type, status: "ok"|"red"|"yellow", elective_slot_group, is_lab, is_pe, is_combined, requires_consecutive, student_group_id, student_group_name} */
  const [allocs, setAllocs] = useState([]);

  /* drag state — custom pointer-based drag (HTML5 drag was causing Chrome
     on Windows to paint a viewport-sized white ghost over the editor). */
  const dragRef = useRef(null);          // {sourceType, offering, faculty_id, room_id, from, siblings, startX, startY, started}
  const [dragPreview, setDragPreview] = useState(null);  // {x, y, code, color, name}
  const [hoverCell, setHoverCell] = useState(null);      // "day-slot" string

  /* per-cell loading ring */
  const [busyCell, setBusyCell] = useState(null);    // "day-slot"

  /* room picker modal */
  const [roomPicker, setRoomPicker] = useState(null);
  // { day, slot, targetSlots, offering, freeRooms: [], loading, conflict_room_id? }

  /* exit confirm modal */
  const [exitModal, setExitModal] = useState(null);  // {dirty, dest}

  /* save state */
  const [saving, setSaving] = useState(false);
  const [toast,  setToast]  = useState(null);  // {kind, text}

  /* ─── load everything + create draft ─── */
  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        setLoading(true);
        // 1. Load base data
        const [ttR, sgR, facR] = await Promise.all([
          api.get(`scheduler/timetables/${timetableId}/`),
          api.get(`academics/student-groups/${sectionId}/`),
          api.get(`faculty/faculty/`),
        ]);
        if (cancelled) return;

        setTimetable(ttR.data);
        setSection(sgR.data);
        setFaculties(asList(facR.data));

        // 2. Create a draft copy of the timetable for real-time editing
        const startResp = await api.post("scheduler/editor/start/", {
          base_timetable_id: Number(timetableId),
          student_group_id:  Number(sectionId),
        });
        if (cancelled) return;

        const draft = startResp.data;
        setDraftId(draft.draft_timetable_id);

        // 3. Load palette with draft-accurate counts
        const palR = await api.get(
          `scheduler/editor/palette/?student_group_id=${sectionId}&timetable_id=${draft.draft_timetable_id}`
        );
        if (cancelled) return;
        setOfferings(palR.data.offerings || []);

        // 4. Normalize allocations from the draft
        const rows = (draft.allocations || []).map(normaliseAlloc);
        setAllocs(rows);
        initialAllocsRef.current = JSON.stringify(rows.map(snapshotRow));
      } catch (e) {
        if (!cancelled) {
          console.error(e);
          setError("Failed to load editor. Check backend connection.");
        }
      } finally {
        if (!cancelled) setLoading(false);
      }
    })();
    return () => { cancelled = true; };
  }, [timetableId, sectionId]);

  /* ─── colour map per course (consistent with viewer) ─── */
  const colorMap = useMemo(() => {
    const codes = [...new Set(allocs.map((a) => a.course_code))].sort();
    const map = {};
    codes.forEach((code, i) => { map[code] = PALETTE[i % PALETTE.length]; });
    // include palette items not yet placed so palette cards have colors
    offerings.forEach((o, i) => {
      if (!map[o.course_code]) {
        map[o.course_code] = PALETTE[(codes.length + i) % PALETTE.length];
      }
    });
    return map;
  }, [allocs, offerings]);

  /* working-days filter */
  const activeDays = useMemo(() => {
    const wd = section?.working_days;
    if (Array.isArray(wd) && wd.length > 0) return ALL_DAYS.filter((d) => wd.includes(d));
    return ALL_DAYS.slice(0, 5);
  }, [section]);

  /* grid index */
  const grid = useMemo(() => {
    const g = {};
    activeDays.forEach((d) => {
      g[d] = {};
      [1, 2, 3, 4, 5, 6].forEach((s) => { g[d][s] = []; });
    });
    allocs.forEach((a) => {
      if (g[a.day]?.[a.slot] !== undefined) g[a.day][a.slot].push(a);
    });
    return g;
  }, [allocs, activeDays]);

  /* ─── derived offering counts (live, includes pending edits) ─── */
  const scheduledByOffering = useMemo(() => {
    const m = {};
    allocs.forEach((a) => {
      if (!a.course_offering_id) return;
      m[a.course_offering_id] = (m[a.course_offering_id] || 0) + 1;
    });
    return m;
  }, [allocs]);

  /* dirty? */
  const isDirty = useMemo(() => {
    if (!initialAllocsRef.current) return false;
    return JSON.stringify(allocs.map(snapshotRow)) !== initialAllocsRef.current;
  }, [allocs]);

  /* ─── pointer-based drag system (replaces HTML5 drag) ────── */

  // Begin a potential drag — actual dragging starts once the pointer moves
  // past a small threshold. This avoids triggering drag on simple clicks.
  const startPointerDrag = (e, payload) => {
    if (e.button !== undefined && e.button !== 0) return;   // left-click only
    e.preventDefault();
    dragRef.current = {
      ...payload,
      startX:  e.clientX,
      startY:  e.clientY,
      started: false,
    };
    document.addEventListener("pointermove", onDocumentPointerMove);
    document.addEventListener("pointerup",   onDocumentPointerUp,   { once: true });
    document.addEventListener("pointercancel", onDocumentPointerUp, { once: true });
  };

  const beginPaletteDrag = (e, offering) => {
    let siblings = [];
    if (offering.elective_slot_group) {
      siblings = offerings.filter(o => o.elective_slot_group === offering.elective_slot_group);
    } else {
      siblings = [offering];
    }
    
    startPointerDrag(e, {
      sourceType: "palette",
      offering,
      faculty_id: offering.faculty_id,
      room_id:    null,
      from:       null,
      siblings,
      previewCode: offering.course_code,
      previewName: offering.course_name,
      previewColor: colorFor(offering.course_code, colorMap),
    });
  };

  const beginCellDrag = (e, row) => {
    // collect siblings (lab pair / PE bundle / single row)
    let siblings;
    if (row.is_lab || row.requires_consecutive) {
      siblings = allocs.filter((a) =>
        a.day === row.day &&
        a.course_offering_id === row.course_offering_id &&
        Math.abs(a.slot - row.slot) <= 1,
      );
    } else if (row.elective_slot_group) {
      siblings = allocs.filter((a) =>
        a.day === row.day && a.slot === row.slot &&
        a.elective_slot_group === row.elective_slot_group,
      );
    } else {
      siblings = [row];
    }
    const anchor = siblings.reduce((m, s) => (s.slot < m.slot ? s : m), siblings[0]);

    startPointerDrag(e, {
      sourceType: "cell",
      offering: {
        id:                   anchor.course_offering_id,
        course_code:          anchor.course_code,
        course_name:          anchor.course_name,
        course_type:          anchor.course_type,
        faculty_id:           anchor.faculty_id,
        faculty_name:         anchor.faculty_name,
        is_pe:                anchor.is_pe,
        is_lab:               anchor.is_lab,
        is_combined:          anchor.is_combined,
        elective_slot_group:  anchor.elective_slot_group,
        combined_token:       anchor.combined_token,
        requires_consecutive: anchor.requires_consecutive,
        student_group_id:     anchor.student_group_id,
        room_type_hint:       anchor.room_type === "LAB" ? "LAB" : "THEORY",
      },
      faculty_id: anchor.faculty_id,
      room_id:    anchor.room_id,
      from:       { day: anchor.day, slot: anchor.slot },
      siblings,
      previewCode: anchor.course_code,
      previewName: anchor.course_name,
      previewColor: colorFor(anchor.course_code, colorMap),
    });
  };

  // Handlers must keep stable identity for add/removeEventListener, so they
  // live in refs.
  const onDocumentPointerMoveRef = useRef();
  const onDocumentPointerUpRef = useRef();

  onDocumentPointerMoveRef.current = (e) => {
    const d = dragRef.current;
    if (!d) return;
    const dx = e.clientX - d.startX;
    const dy = e.clientY - d.startY;
    if (!d.started) {
      if (dx * dx + dy * dy < 25) return;   // 5px threshold
      d.started = true;
    }
    setDragPreview({
      x: e.clientX, y: e.clientY,
      code: d.previewCode,
      name: d.previewName,
      color: d.previewColor,
    });
    // detect cell under cursor
    const el = document.elementFromPoint(e.clientX, e.clientY);
    const cell = el && el.closest && el.closest("[data-cellkey]");
    if (cell) setHoverCell(cell.dataset.cellkey);
    else      setHoverCell(null);
  };

  onDocumentPointerUpRef.current = (e) => {
    document.removeEventListener("pointermove", onDocumentPointerMove);
    const d = dragRef.current;
    if (!d) { setDragPreview(null); setHoverCell(null); return; }
    if (!d.started) {
      // wasn't a real drag — just a click; clean up
      dragRef.current = null;
      setDragPreview(null);
      setHoverCell(null);
      return;
    }
    // find target cell
    const el = document.elementFromPoint(e.clientX, e.clientY);
    const cell = el && el.closest && el.closest("[data-cellkey]");
    setDragPreview(null);
    setHoverCell(null);
    if (!cell) { dragRef.current = null; return; }
    const [day, slotStr] = cell.dataset.cellkey.split("-");
    const slot = Number(slotStr);
    runDrop(day, slot);
  };

  // Stable wrappers — same identity across renders.
  function onDocumentPointerMove(e) { onDocumentPointerMoveRef.current(e); }
  function onDocumentPointerUp(e)   { onDocumentPointerUpRef.current(e); }

  /* ─── drop handler — POST to /editor/move/ ─── */
  const runDrop = useCallback(async (day, slot) => {
    if (!dragRef.current) return;
    const dragInfo = dragRef.current;
    dragRef.current = null;

    if (!draftId) {
      setToast({ kind: "error", text: "Editor not ready — draft not created yet." });
      return;
    }

    // ── ignore drop if it's the exact same position it came from ──
    if (dragInfo.from?.day === day && dragInfo.from?.slot === slot) {
      return;
    }

    const isLab = dragInfo.offering.is_lab || dragInfo.offering.requires_consecutive;
    // lab needs (slot, slot+1) within same day, must be a valid LAB_PAIR
    if (isLab && !isLabPair(slot)) {
      setToast({ kind: "error", text: `Lab needs 2 consecutive slots — slot ${slot} can't pair with slot ${slot + 1} (lunch in between or end of day).` });
      return;
    }

    // ── quick client-side occupied-slot check (instant UX feedback) ──
    const targetSlots = isLab ? [slot, slot + 1] : [slot];
    const sourceDay   = dragInfo.from?.day;
    const sourceSlots = new Set((dragInfo.siblings || []).map((s) => s.slot));
    const occupiedConflict = allocs.find((a) =>
      a.day === day &&
      targetSlots.includes(a.slot) &&
      a.student_group_id === Number(sectionId) &&
      !(a.day === sourceDay && sourceSlots.has(a.slot)),  // ignore the card being moved
    );
    if (occupiedConflict) {
      // PE stacking is OK — same elective_slot_group can share a slot
      const isPEStacking = dragInfo.offering.is_pe && dragInfo.offering.elective_slot_group &&
        occupiedConflict.elective_slot_group === dragInfo.offering.elective_slot_group;
      if (!isPEStacking) {
        setToast({
          kind: "error",
          text: `${DAY_FULL[day]} S${occupiedConflict.slot} is occupied by ${occupiedConflict.course_code}. Remove it first.`,
        });
        return;
      }
    }

    setBusyCell(cellKey(day, slot));

    try {
      // ── POST to /editor/move/ — server does ALL constraint checking ──
      const payload = {
        draft_timetable_id: draftId,
        student_group_id:   Number(sectionId),
        course_offering_id: dragInfo.offering.id,
        action:             "move",
        source: dragInfo.from ? {
          day:  dragInfo.from.day,
          slot: dragInfo.from.slot,
        } : null,
        target: { day, slot },
      };

      const resp = await api.post("scheduler/editor/move/", payload);
      const data = resp.data;

      if (!data.ok) {
        // Show errors as toast — take the first one
        const msg = data.errors?.map((e) => e.message).join(" · ") || "Move blocked.";
        setToast({ kind: "error", text: msg });
        // Refresh allocs from server in case state diverged
        if (data.allocations) setAllocs(data.allocations.map(normaliseAlloc));
        return;
      }

      // ── Success: update client state from server response ──
      setAllocs(data.allocations.map(normaliseAlloc));

      // ── Room warnings? Open room picker ──
      if (data.warnings?.length > 0 || dragInfo.sourceType === "palette") {
        const hasRoomWarning = data.warnings?.some((w) => w.type === "room_busy");
        const needsRoom = dragInfo.sourceType === "palette" || hasRoomWarning;
        if (needsRoom) {
          setRoomPicker({
            day, slot,
            targetSlots,
            offering: dragInfo.offering,
            conflict_room_id: hasRoomWarning ? dragInfo.room_id : null,
            loading: true,
            freeRooms: [],
          });
        }
      }

      if (!data.warnings?.length && dragInfo.sourceType !== "palette") {
        setToast({ kind: "ok", text: `Moved ${dragInfo.offering.course_code} to ${DAY_FULL[day]} S${slot}${isLab ? `–S${slot + 1}` : ""}.` });
      }
    } catch (err) {
      console.error(err);
      const msg = err?.response?.data?.error || err?.response?.data?.errors?.[0]?.message || "Move failed. Try again.";
      setToast({ kind: "error", text: msg });
    } finally {
      setBusyCell(null);
    }
  }, [draftId, sectionId, allocs]);

  /* ─── load free rooms when picker opens ─── */
  useEffect(() => {
    if (!roomPicker || !roomPicker.loading) return;
    let cancelled = false;
    (async () => {
      try {
        const offering = roomPicker.offering;
        const room_type = offering.is_lab ? "LAB" : "THEORY";
        const minCap = section?.strength || 0;
        // Use draft timetable ID for accurate room availability
        const ttIdForRooms = draftId || timetableId;
        // query free rooms PER target slot, then intersect
        const perSlot = await Promise.all(roomPicker.targetSlots.map((ts) =>
          api.get(`scheduler/editor/rooms/`, {
            params: {
              day: roomPicker.day,
              slot: ts,
              timetable_id: ttIdForRooms,
              room_type,
              min_capacity: minCap,
            },
          }).then((r) => r.data.rooms || []),
        ));
        const idSets = perSlot.map((arr) => new Set(arr.map((r) => r.id)));
        const intersection = perSlot[0]?.filter((r) => idSets.every((s) => s.has(r.id))) || [];

        if (!cancelled) {
          setRoomPicker((rp) => rp ? { ...rp, freeRooms: intersection, loading: false } : rp);
        }
      } catch (err) {
        console.error(err);
        if (!cancelled) {
          setRoomPicker((rp) => rp ? { ...rp, freeRooms: [], loading: false } : rp);
        }
      }
    })();
    return () => { cancelled = true; };
  }, [roomPicker?.loading, draftId, timetableId, section]);

  /* ─── apply a room from picker → POST /editor/move/ with assign_room ─── */
  const applyRoom = async (room) => {
    if (!roomPicker || !draftId) return;
    const { day, slot, targetSlots, offering } = roomPicker;

    try {
      const resp = await api.post("scheduler/editor/move/", {
        draft_timetable_id: draftId,
        student_group_id:   Number(sectionId),
        course_offering_id: offering.id,
        action:             "assign_room",
        target:             { day, slot },
        room_id:            room.id,
      });

      if (resp.data.ok) {
        setAllocs(resp.data.allocations.map(normaliseAlloc));
        setRoomPicker(null);
        setToast({ kind: "ok", text: `Assigned ${room.building_code}-${room.room_number}.` });
      } else {
        setToast({ kind: "error", text: resp.data.errors?.[0]?.message || "Room assignment failed." });
      }
    } catch (err) {
      console.error(err);
      setToast({ kind: "error", text: "Room assignment failed." });
    }
  };

  /* ─── delete a placed allocation → POST /editor/delete/ ─── */
  const deleteAlloc = async (row) => {
    if (!draftId) return;

    try {
      const resp = await api.post("scheduler/editor/delete/", {
        draft_timetable_id: draftId,
        student_group_id:   Number(sectionId),
        course_offering_id: row.course_offering_id,
        day:                row.day,
        slot:               row.slot,
      });

      if (resp.data.ok) {
        setAllocs(resp.data.allocations.map(normaliseAlloc));
        setToast({ kind: "ok", text: `Removed ${row.course_code} from ${DAY_FULL[row.day]} S${row.slot}.` });
      }
    } catch (err) {
      console.error(err);
      setToast({ kind: "error", text: "Delete failed." });
    }
  };

  /* ─── save → promote draft to real version ─── */
  const onSave = async () => {
    if (!draftId) return;

    // any reds (no room) prevent save
    const reds = allocs.filter((r) => r.status !== "ok" && r.student_group_id === Number(sectionId));
    if (reds.length > 0) {
      setToast({ kind: "error", text: `${reds.length} card(s) missing a room. Click each red card to assign a room first.` });
      return;
    }
    try {
      setSaving(true);
      const resp = await api.post("scheduler/editor/save/", {
        draft_timetable_id: draftId,
        student_group_id:   Number(sectionId),
      });
      if (resp.data.ok) {
        setToast({ kind: "ok", text: `Saved as v${resp.data.version}.` });
        initialAllocsRef.current = JSON.stringify(allocs.map(snapshotRow));
        // Navigate to the saved version for further edits
        setTimeout(() => {
          navigate(`/timetable-editor/${resp.data.timetable_id}/${sectionId}`, { replace: true });
        }, 600);
      } else {
        setToast({ kind: "error", text: resp.data.error || "Save failed." });
      }
    } catch (err) {
      console.error(err);
      const msg = err?.response?.data?.error || "Save failed.";
      setToast({ kind: "error", text: msg });
    } finally {
      setSaving(false);
    }
  };

  /* ─── exit logic — discard draft on exit ─── */
  const requestExit = () => {
    if (isDirty) setExitModal({ dest: "/generated" });
    else discardAndExit("/generated");
  };

  const discardAndExit = async (dest) => {
    if (draftId) {
      try {
        await api.post("scheduler/editor/discard/", { draft_timetable_id: draftId });
      } catch {
        // ignore discard errors — draft will be auto-cleaned
      }
    }
    navigate(dest);
  };

  /* ─── cleanup draft on unmount (browser close, navigation) ─── */
  useEffect(() => {
    const handleBeforeUnload = () => {
      if (draftId) {
        // Use sendBeacon for reliability during page unload
        const data = JSON.stringify({ draft_timetable_id: draftId });
        const blob = new Blob([data], { type: "application/json" });
        navigator.sendBeacon("/api/scheduler/editor/discard/", blob);
      }
    };
    window.addEventListener("beforeunload", handleBeforeUnload);
    return () => {
      window.removeEventListener("beforeunload", handleBeforeUnload);
      // Also discard on React unmount (SPA navigation away without save)
      if (draftId) {
        api.post("scheduler/editor/discard/", { draft_timetable_id: draftId }).catch(() => {});
      }
    };
  }, [draftId]);

  /* ─── render: loading / error states ─── */
  if (loading) {
    return (
      <div className="editor-shell">
        <div className="editor-loader"><div className="ring" />Loading editor…</div>
      </div>
    );
  }
  if (error) {
    return (
      <div className="editor-shell">
        <div className="editor-error">
          <p>{error}</p>
          <button className="btn-primary" onClick={() => navigate("/generated")}>Back</button>
        </div>
      </div>
    );
  }

  /* ─── render: main editor ─── */
  /* lab-span detection: if slot S has a lab allocation and slot S+1 has the same course, render the S
     cell with colSpan=2 and skip rendering S+1 entirely. */
  const labSpans = {};
  activeDays.forEach((d) => {
    [1, 2, 3, 4, 5].forEach((s) => {
      const here = grid[d][s] || [];
      const next = grid[d][s + 1] || [];
      if (
        here.length > 0 &&
        here.some((r) => (r.is_lab || r.requires_consecutive) && next.some((n) => n.course_offering_id === r.course_offering_id))
      ) {
        labSpans[cellKey(d, s)] = true;
        labSpans[`skip-${cellKey(d, s + 1)}`] = true;
      }
    });
  });

  return (
    <div className="editor-shell">
      {/* ── header bar ── */}
      <header className="editor-header">
        <button className="editor-exit" onClick={requestExit}>
          <span className="editor-exit-arrow">←</span> Back
        </button>
        <div className="editor-title">
          <strong>Editing: {section?.name || sectionId}</strong>
          <span className="editor-sub">
            v{timetable?.version}
            {isDirty && <em className="editor-dirty"> · unsaved changes</em>}
          </span>
        </div>
        <button
          className="editor-save"
          disabled={saving || !isDirty}
          onClick={onSave}
        >{saving ? "Saving…" : "💾 Save"}</button>
      </header>

      {/* ── body: palette sidebar + grid ── */}
      <div className="editor-body">
        {/* ── palette sidebar ── */}
        <aside className="editor-palette">
          <span className="palette-label">Course Palette</span>
          <p className="palette-hint">Drag a card onto the grid to schedule it.</p>
          <div className="palette-list">
            {offerings.map((o) => {
              const placedSlots = scheduledByOffering[o.id] || 0;
              const isLab = o.is_lab || o.requires_consecutive;
              const placedSessions = isLab ? Math.ceil(placedSlots / 2) : placedSlots;
              const c = colorFor(o.course_code, colorMap);
              return (
                <div
                  key={o.id}
                  className="palette-card"
                  style={{
                    background: c.bg,
                    borderLeftColor: c.border,
                    cursor: "grab",
                  }}
                  onPointerDown={(e) => beginPaletteDrag(e, o)}
                >
                  <div className="pc-top">
                    <span className="pc-code" style={{ color: c.border }}>{o.course_code}</span>
                    {o.is_lab && <span className="pc-tag lab">Lab</span>}
                    {o.is_pe  && <span className="pc-tag pe">PE</span>}
                  </div>
                  <div className="pc-name">{o.course_name}</div>
                  <div className="pc-faculty">{o.faculty_name || "—"}</div>
                  <div className="pc-count">
                    <span className={placedSessions >= o.weekly_load ? "ok" : "left"}>{placedSessions}/{o.weekly_load}</span>
                  </div>
                </div>
              );
            })}
          </div>
        </aside>

        {/* ── timetable grid ── */}
        <div className="editor-grid-wrap">
          <table className="editor-grid">
            <thead>
              <tr>
                <th className="day-col">DAY</th>
                {[1, 2, 3, 4].map((s) => (
                  <th key={s}>
                    <span className="sl-n">S{s}</span>
                    <span className="sl-t">{SLOT_TIMES[s]}</span>
                  </th>
                ))}
                <th className="lunch-col">LUNCH<br/><span className="sl-t">13:20–14:15</span></th>
                {[5, 6].map((s) => (
                  <th key={s}>
                    <span className="sl-n">S{s}</span>
                    <span className="sl-t">{SLOT_TIMES[s]}</span>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {activeDays.map((d) => {
                return (
                <tr key={d}>
                  <td className="day-col day-label">{d}</td>
                  {[1, 2, 3, 4].map((s) => {
                    if (labSpans[`skip-${cellKey(d, s)}`]) return null;
                    const span = labSpans[cellKey(d, s)] ? 2 : 1;
                    return (
                      <DropCell
                        key={s}
                        day={d}
                        slot={s}
                        rows={grid[d]?.[s] || []}
                        hover={hoverCell === cellKey(d, s) || (span === 2 && hoverCell === cellKey(d, s + 1))}
                        busy={busyCell === cellKey(d, s)}
                        colSpan={span}
                        onStartCellDrag={(e, row) => beginCellDrag(e, row)}
                        onCardClick={(row) => {
                          if (row.status === "ok") return;
                          const isLab = row.is_lab || row.requires_consecutive;
                          const targetSlots = isLab ? [row.slot, row.slot + 1] : [row.slot];
                          setRoomPicker({
                            day: row.day, slot: row.slot,
                            targetSlots,
                            offering: {
                              id: row.course_offering_id,
                              course_code: row.course_code,
                              course_name: row.course_name,
                              course_type: row.course_type,
                              faculty_id:  row.faculty_id,
                              faculty_name: row.faculty_name,
                              is_lab: row.is_lab,
                              is_pe:  row.is_pe,
                              is_combined: row.is_combined,
                              elective_slot_group: row.elective_slot_group,
                              combined_token: row.combined_token,
                              requires_consecutive: row.requires_consecutive,
                              room_type_hint: row.is_lab ? "LAB" : "THEORY",
                              student_group_id: row.student_group_id,
                            },
                            conflict_room_id: row.status === "yellow" ? row.room_id : null,
                            loading: true,
                            freeRooms: [],
                          });
                        }}
                        onDelete={deleteAlloc}
                        colorMap={colorMap}
                      />
                    );
                  })}
                  <td className="lunch-col">🍽</td>
                  {[5, 6].map((s) => {
                    if (labSpans[`skip-${cellKey(d, s)}`]) return null;
                    const span = labSpans[cellKey(d, s)] ? 2 : 1;
                    return (
                      <DropCell
                        key={s}
                        day={d}
                        slot={s}
                        rows={grid[d]?.[s] || []}
                        hover={hoverCell === cellKey(d, s) || (span === 2 && hoverCell === cellKey(d, s + 1))}
                        busy={busyCell === cellKey(d, s)}
                        colSpan={span}
                        onStartCellDrag={(e, row) => beginCellDrag(e, row)}
                        onCardClick={(row) => {
                          if (row.status === "ok") return;
                          const isLab = row.is_lab || row.requires_consecutive;
                          const targetSlots = isLab ? [row.slot, row.slot + 1] : [row.slot];
                          setRoomPicker({
                            day: row.day, slot: row.slot,
                            targetSlots,
                            offering: {
                              id: row.course_offering_id,
                              course_code: row.course_code,
                              course_name: row.course_name,
                              course_type: row.course_type,
                              faculty_id:  row.faculty_id,
                              faculty_name: row.faculty_name,
                              is_lab: row.is_lab,
                              is_pe:  row.is_pe,
                              is_combined: row.is_combined,
                              elective_slot_group: row.elective_slot_group,
                              combined_token: row.combined_token,
                              requires_consecutive: row.requires_consecutive,
                              room_type_hint: row.is_lab ? "LAB" : "THEORY",
                              student_group_id: row.student_group_id,
                            },
                            conflict_room_id: row.status === "yellow" ? row.room_id : null,
                            loading: true,
                            freeRooms: [],
                          });
                        }}
                        onDelete={deleteAlloc}
                        colorMap={colorMap}
                      />
                    );
                  })}
                </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </div>

      {/* ── room picker modal ── */}
      {roomPicker && (
        <RoomPickerModal
          state={roomPicker}
          onPick={applyRoom}
          onClose={() => setRoomPicker(null)}
        />
      )}

      {/* ── exit confirm ── */}
      {exitModal && (
        <div className="editor-modal-backdrop" onClick={() => setExitModal(null)}>
          <div className="editor-modal" onClick={(e) => e.stopPropagation()}>
            <h3>Unsaved changes</h3>
            <p>You have unsaved edits. Save them as a new version before leaving?</p>
            <div className="modal-actions">
              <button className="btn-ghost" onClick={() => discardAndExit(exitModal.dest)}>Discard</button>
              <button className="btn-ghost" onClick={() => setExitModal(null)}>Cancel</button>
              <button
                className="btn-primary"
                onClick={async () => {
                  await onSave();
                  navigate(exitModal.dest);
                }}
              >Save &amp; exit</button>
            </div>
          </div>
        </div>
      )}

      {/* ── floating drag preview (follows cursor) ── */}
      {dragPreview && (
        <div
          className={`drag-preview ${dragRef.current?.siblings?.length > 1 ? 'is-stacked' : ''}`}
          style={{
            left: dragPreview.x + 14,
            top:  dragPreview.y + 14,
            background: dragPreview.color?.bg,
            borderColor: dragPreview.color?.border,
            color: dragPreview.color?.border,
          }}
        >
          <strong>{dragPreview.code}</strong>
          <span>{dragPreview.name}</span>
          {dragRef.current?.siblings?.length > 1 && (
            <div style={{ marginTop: 4, fontSize: '0.75rem', fontWeight: 600, opacity: 0.8 }}>
              + {dragRef.current.siblings.length - 1} tied course{dragRef.current.siblings.length > 2 ? 's' : ''} moving together
            </div>
          )}
        </div>
      )}

      {/* ── toast ── */}
      {toast && <Toast kind={toast.kind} text={toast.text} onClose={() => setToast(null)} />}
    </div>
  );
}

/* ─────────────────────────────────────────────────────────────
   Sub-components
   ───────────────────────────────────────────────────────────── */

function DropCell({ day, slot, rows, hover, busy, colSpan = 1, onStartCellDrag, onCardClick, onDelete, colorMap }) {
  const ck = `${day}-${slot}`;
  // De-duplicate rows when a lab spans 2 cells: only show the FIRST half once.
  const visibleRows = rows.filter((r, i, arr) => {
    if (!(r.is_lab || r.requires_consecutive)) return true;
    return !arr.some((s, j) =>
      j < i &&
      (s.is_lab || s.requires_consecutive) &&
      s.course_offering_id === r.course_offering_id &&
      s.day === r.day &&
      s.slot < r.slot,
    );
  });
  return (
    <td
      colSpan={colSpan}
      data-cellkey={ck}
      className={`drop-cell${rows.length ? " has-row" : ""}${hover ? " is-hover" : ""}${busy ? " is-busy" : ""}${colSpan === 2 ? " lab-span" : ""}`}
    >
      {busy && <div className="cell-spinner"><div className="ring small" /></div>}
      {visibleRows.map((r) => (
        <SlotCard
          key={r.id}
          row={r}
          color={colorMap[r.course_code]}
          onStartDrag={onStartCellDrag}
          onClick={() => onCardClick(r)}
          onDelete={() => onDelete(r)}
        />
      ))}
    </td>
  );
}

function SlotCard({ row, color, onStartDrag, onClick, onDelete }) {
  const c = color || PALETTE[0];
  const tone = row.status === "red"    ? "card-red"
             : row.status === "yellow" ? "card-yellow"
             : "";
  return (
    <div
      className={`slot-card ${tone}`}
      onPointerDown={(e) => onStartDrag(e, row)}
      onClick={onClick}
      style={{
        background: c.bg,
        borderLeftColor: c.border,
      }}
      title={row.status === "red" ? "Click to assign a room" :
             row.status === "yellow" ? "Click to reassign room (current room is in use)" :
             "Drag to move · click delete to remove"}
    >
      <button
        type="button"
        className="card-x"
        onClick={(e) => { e.stopPropagation(); onDelete(); }}
        title="Remove"
      >×</button>
      <div className="sc-code" style={{ color: c.border }}>
        {row.course_code}
        {row.is_lab && <span className="sc-tag lab">Lab</span>}
        {row.is_pe  && <span className="sc-tag pe">PE</span>}
        {row.is_combined && <span className="sc-tag combined">A+B</span>}
      </div>
      <div className="sc-name">{row.course_name}</div>
      <div className="sc-faculty">{row.faculty_name || "—"}</div>
      <div className="sc-room">
        {row.status === "red"
          ? <span className="needs-room">⚠ Assign room</span>
          : row.status === "yellow"
            ? <span className="needs-room">⚠ Room clash — pick another</span>
            : <span>{row.building_code ? `${row.building_code}-${row.room_number}` : row.room_number}</span>}
      </div>
    </div>
  );
}

function RoomPickerModal({ state, onPick, onClose }) {
  return (
    <div className="editor-modal-backdrop" onClick={onClose}>
      <div className="editor-modal rooms-modal" onClick={(e) => e.stopPropagation()}>
        <h3>
          {state.conflict_room_id ? "Reassign room" : "Assign a room"}
        </h3>
        <p className="rooms-sub">
          <strong>{state.offering.course_code}</strong> · {state.offering.course_name}
          <br />
          {DAY_FULL[state.day]} · Slot{state.targetSlots.length > 1 ? `s ${state.targetSlots.join(" + ")}` : ` ${state.targetSlots[0]}`}
          {" · "}
          {state.offering.is_lab ? "Laboratory" : "Theory classroom"}
        </p>

        {state.loading ? (
          <div className="rooms-loading"><div className="ring" />Checking room availability…</div>
        ) : state.freeRooms.length === 0 ? (
          <div className="rooms-empty">
            No rooms free in this slot.
            <em> Try a different slot or change the room type filter.</em>
          </div>
        ) : (
          <div className="rooms-list">
            {state.freeRooms.map((r) => (
              <button key={r.id} type="button" className="room-pill" onClick={() => onPick(r)}>
                <span className="rp-num">{r.building_code}-{r.room_number}</span>
                <span className="rp-meta">{r.room_type} · Cap {r.capacity}</span>
              </button>
            ))}
          </div>
        )}

        <div className="modal-actions">
          <button className="btn-ghost" onClick={onClose}>Cancel</button>
        </div>
      </div>
    </div>
  );
}

function Toast({ kind, text, onClose }) {
  useEffect(() => {
    const t = setTimeout(onClose, kind === "error" ? 5000 : 2400);
    return () => clearTimeout(t);
  }, [kind, onClose]);
  return (
    <div className={`editor-toast toast-${kind}`}>
      <span>{text}</span>
      <button onClick={onClose}>×</button>
    </div>
  );
}

/* ─── utility: minimal diff key for dirty-detection ─── */
function snapshotRow(r) {
  return [r.day, r.slot, r.course_offering_id, r.faculty_id, r.room_id, r.status].join("|");
}

export default TimetableEditorPage;
