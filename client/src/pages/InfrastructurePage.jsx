import { useCallback, useEffect, useMemo, useState } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import BulkUploadCard from "../components/BulkUploadCard";
import { toBoolean, toNumber } from "../utils/spreadsheet";
import { asList, extractError } from "../utils/helpers";
import {
  FaTrash, FaEdit, FaTimes, FaPlus, FaBuilding,
  FaChevronDown, FaChevronRight, FaDoorOpen, FaFlask,
  FaCheckCircle, FaSearch, FaLayerGroup,
} from "react-icons/fa";

const ROOM_TYPE_META = {
  THEORY: { label: "Theory Room", color: "#6366f1", bg: "rgba(99,102,241,0.1)", icon: FaDoorOpen },
  LAB:    { label: "Laboratory",  color: "#14b8a6", bg: "rgba(20,184,166,0.1)",  icon: FaFlask  },
};

const INIT_BUILDING = { name: "", code: "", floors: 1, is_active: true };
const INIT_ROOM = {
  building: "", room_number: "", floor: 1, capacity: 40,
  room_type: "THEORY", is_active: true, is_shared: true, priority_weight: 1,
};

function InfrastructurePage() {
  const [buildings, setBuildings]           = useState([]);
  const [rooms, setRooms]                   = useState([]);
  const [loading, setLoading]               = useState(true);
  const [search, setSearch]                 = useState("");

  // form visibility
  const [showBuildingForm, setShowBuildingForm] = useState(false);
  const [showRoomForm, setShowRoomForm]         = useState(false);

  // alerts
  const [buildingError,   setBuildingError]   = useState("");
  const [buildingSuccess, setBuildingSuccess] = useState("");
  const [roomError,       setRoomError]       = useState("");
  const [roomSuccess,     setRoomSuccess]     = useState("");

  // submitting
  const [submittingBuilding, setSubmittingBuilding] = useState(false);
  const [submittingRoom,     setSubmittingRoom]     = useState(false);

  // forms
  const [buildingForm, setBuildingForm] = useState(INIT_BUILDING);
  const [roomForm,     setRoomForm]     = useState(INIT_ROOM);

  // edit ids
  const [editBuildingId, setEditBuildingId] = useState(null);
  const [editRoomId,     setEditRoomId]     = useState(null);

  // hierarchy expand
  const [expandedBuildings, setExpandedBuildings] = useState({});
  const [expandedFloors,    setExpandedFloors]    = useState({});

  /* ── load ── */
  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [bRes, rRes] = await Promise.all([
        api.get("infrastructure/building/"),
        api.get("infrastructure/room/"),
      ]);
      setBuildings(asList(bRes.data));
      setRooms(asList(rRes.data));
    } catch (err) {
      console.error("Failed to load infrastructure:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => { loadData(); }, [loadData]);

  /* ── building submit ── */
  const handleBuildingSubmit = async (e) => {
    e.preventDefault();
    setBuildingError(""); setBuildingSuccess(""); setSubmittingBuilding(true);
    try {
      const payload = { ...buildingForm, floors: Number(buildingForm.floors) };
      if (editBuildingId) {
        await api.patch(`infrastructure/building/${editBuildingId}/`, payload);
        setBuildingSuccess("Building updated successfully.");
        setEditBuildingId(null);
      } else {
        await api.post("infrastructure/building/", payload);
        setBuildingSuccess("Building added successfully.");
      }
      setBuildingForm(INIT_BUILDING);
      setShowBuildingForm(false);
      loadData();
    } catch (err) {
      setBuildingError(extractError(err, editBuildingId ? "Failed to update building." : "Failed to add building."));
    } finally {
      setSubmittingBuilding(false);
    }
  };

  const handleBuildingEdit = (b) => {
    setEditBuildingId(b.id);
    setBuildingForm({ name: b.name, code: b.code, floors: b.floors, is_active: b.is_active });
    setBuildingError(""); setBuildingSuccess("");
    setShowBuildingForm(true);
  };

  const cancelBuildingEdit = () => {
    setEditBuildingId(null); setBuildingForm(INIT_BUILDING);
    setBuildingError(""); setBuildingSuccess(""); setShowBuildingForm(false);
  };

  const handleBuildingDelete = async (id) => {
    if (!window.confirm("Delete this building and all its rooms?")) return;
    try { await api.delete(`infrastructure/building/${id}/`); loadData(); }
    catch (err) { setBuildingError(extractError(err, "Failed to delete building.")); }
  };

  /* ── room submit ── */
  const handleRoomSubmit = async (e) => {
    e.preventDefault();
    setRoomError(""); setRoomSuccess(""); setSubmittingRoom(true);
    try {
      const payload = {
        ...roomForm,
        building: Number(roomForm.building),
        floor: Number(roomForm.floor),
        capacity: Number(roomForm.capacity),
        priority_weight: Number(roomForm.priority_weight),
      };
      if (editRoomId) {
        await api.patch(`infrastructure/room/${editRoomId}/`, payload);
        setRoomSuccess("Room updated successfully.");
        setEditRoomId(null);
      } else {
        await api.post("infrastructure/room/", payload);
        setRoomSuccess("Room added successfully.");
      }
      setRoomForm(INIT_ROOM);
      setShowRoomForm(false);
      loadData();
    } catch (err) {
      setRoomError(extractError(err, editRoomId ? "Failed to update room." : "Failed to add room."));
    } finally {
      setSubmittingRoom(false);
    }
  };

  const handleRoomEdit = (r) => {
    setEditRoomId(r.id);
    setRoomForm({
      building: r.building || r.building_id || "",
      room_number: r.room_number, floor: r.floor, capacity: r.capacity,
      room_type: r.room_type, is_active: r.is_active,
      is_shared: r.is_shared, priority_weight: r.priority_weight,
    });
    setRoomError(""); setRoomSuccess(""); setShowRoomForm(true);
  };

  const cancelRoomEdit = () => {
    setEditRoomId(null); setRoomForm(INIT_ROOM);
    setRoomError(""); setRoomSuccess(""); setShowRoomForm(false);
  };

  const handleRoomDelete = async (id) => {
    if (!window.confirm("Delete this room?")) return;
    try { await api.delete(`infrastructure/room/${id}/`); loadData(); }
    catch (err) { setRoomError(extractError(err, "Failed to delete room.")); }
  };

  /* ── hierarchy: Building → Floor → Rooms ── */
  const hierarchy = useMemo(() => {
    const q = search.toLowerCase();
    return buildings
      .filter(b => !q || b.name.toLowerCase().includes(q) || b.code.toLowerCase().includes(q))
      .map(b => {
        const bRooms = rooms.filter(r => {
          const match = String(r.building) === String(b.id) || String(r.building_id) === String(b.id);
          if (!match) return false;
          if (!q) return true;
          return r.room_number.toLowerCase().includes(q);
        });
        const floorMap = {};
        bRooms.forEach(r => {
          const f = r.floor ?? 0;
          if (!floorMap[f]) floorMap[f] = [];
          floorMap[f].push(r);
        });
        return { ...b, num_floors: b.floors, bRooms, floorMap };
      });
  }, [buildings, rooms, search]);

  const toggleBuilding = (id) => setExpandedBuildings(p => ({ ...p, [id]: !p[id] }));
  const toggleFloor = (key) => setExpandedFloors(p => ({ ...p, [key]: !p[key] }));

  /* ── stats ── */
  const theoryCount = rooms.filter(r => r.room_type === "THEORY").length;
  const labCount    = rooms.filter(r => r.room_type === "LAB").length;
  const totalCap    = rooms.reduce((s, r) => s + (Number(r.capacity) || 0), 0);

  return (
    <DashboardLayout>

      {/* ── Page Header ── */}
      <div className="sec-page-header">
        <div>
          <h1 className="sec-page-title">Infrastructure</h1>
          <p className="sec-page-sub">Manage buildings and rooms for timetable scheduling.</p>
        </div>
        <div style={{ display: "flex", gap: 10 }}>
          <button
            className="sec-add-btn"
            style={{ background: "linear-gradient(135deg,#059669,#10b981)" }}
            onClick={() => { setShowRoomForm(v => !v); setEditRoomId(null); setRoomForm(INIT_ROOM); }}
          >
            {showRoomForm && !editRoomId ? <><FaTimes /> Close</> : <><FaPlus /> Add Room</>}
          </button>
          <button
            className="sec-add-btn"
            onClick={() => { setShowBuildingForm(v => !v); setEditBuildingId(null); setBuildingForm(INIT_BUILDING); }}
          >
            {showBuildingForm && !editBuildingId ? <><FaTimes /> Close</> : <><FaPlus /> Add Building</>}
          </button>
        </div>
      </div>

      {/* ── Global alerts ── */}
      {buildingError   && <div className="sec-alert sec-alert-error">{buildingError}</div>}
      {buildingSuccess && <div className="sec-alert sec-alert-success">{buildingSuccess}</div>}
      {roomError       && <div className="sec-alert sec-alert-error">{roomError}</div>}
      {roomSuccess     && <div className="sec-alert sec-alert-success">{roomSuccess}</div>}

      {/* ── Building Form Panel ── */}
      {showBuildingForm && (
        <div className="sec-form-panel">
          <div className="sec-form-header">
            <h3>{editBuildingId ? "Update Building" : "Add New Building"}</h3>
          </div>
          <form className="sec-form-grid infra-form-grid" onSubmit={handleBuildingSubmit}>
            <div className="sec-field">
              <label>Building Name <span className="sec-req">*</span></label>
              <input placeholder="e.g. Main Block" value={buildingForm.name} required
                onChange={e => setBuildingForm(p => ({ ...p, name: e.target.value }))} />
            </div>
            <div className="sec-field">
              <label>Building Code <span className="sec-req">*</span></label>
              <input placeholder="e.g. MB" value={buildingForm.code} required
                onChange={e => setBuildingForm(p => ({ ...p, code: e.target.value }))} />
            </div>
            <div className="sec-field">
              <label>No. of Floors</label>
              <input type="number" min="1" value={buildingForm.floors}
                onChange={e => setBuildingForm(p => ({ ...p, floors: e.target.value }))} />
            </div>
            <div className="sec-field" style={{ justifyContent: "flex-end" }}>
              <label className="infra-checkbox-label">
                <input type="checkbox" checked={buildingForm.is_active}
                  onChange={e => setBuildingForm(p => ({ ...p, is_active: e.target.checked }))} />
                <span>Active</span>
              </label>
            </div>
            <div className="sec-form-actions">
              <button type="submit" className="sec-submit-btn" disabled={submittingBuilding}>
                {submittingBuilding ? "Saving…" : editBuildingId ? "Update Building" : "Add Building"}
              </button>
              <button type="button" className="sec-cancel-btn" onClick={cancelBuildingEdit}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* ── Room Form Panel ── */}
      {showRoomForm && (
        <div className="sec-form-panel">
          <div className="sec-form-header">
            <h3>{editRoomId ? "Update Room" : "Add New Room"}</h3>
          </div>
          <form className="sec-form-grid infra-room-form-grid" onSubmit={handleRoomSubmit}>
            <div className="sec-field">
              <label>Building <span className="sec-req">*</span></label>
              <select value={roomForm.building} required
                onChange={e => setRoomForm(p => ({ ...p, building: e.target.value }))}>
                <option value="">— Select Building —</option>
                {buildings.map(b => (
                  <option key={b.id} value={b.id}>{b.name} ({b.code})</option>
                ))}
              </select>
            </div>
            <div className="sec-field">
              <label>Room Number <span className="sec-req">*</span></label>
              <input placeholder="e.g. A201" value={roomForm.room_number} required
                onChange={e => setRoomForm(p => ({ ...p, room_number: e.target.value }))} />
            </div>
            <div className="sec-field">
              <label>Floor</label>
              <input type="number" min="0" value={roomForm.floor}
                onChange={e => setRoomForm(p => ({ ...p, floor: e.target.value }))} />
            </div>
            <div className="sec-field">
              <label>Seating Capacity</label>
              <input type="number" min="1" value={roomForm.capacity}
                onChange={e => setRoomForm(p => ({ ...p, capacity: e.target.value }))} />
            </div>
            <div className="sec-field">
              <label>Room Type</label>
              <select value={roomForm.room_type}
                onChange={e => setRoomForm(p => ({ ...p, room_type: e.target.value }))}>
                <option value="THEORY">Theory Room</option>
                <option value="LAB">Laboratory</option>
              </select>
            </div>
            <div className="sec-field">
              <label>Priority Weight</label>
              <input type="number" min="1" max="10" value={roomForm.priority_weight}
                onChange={e => setRoomForm(p => ({ ...p, priority_weight: e.target.value }))} />
            </div>
            <div className="sec-field" style={{ flexDirection: "row", alignItems: "flex-end", gap: 20 }}>
              <label className="infra-checkbox-label">
                <input type="checkbox" checked={roomForm.is_shared}
                  onChange={e => setRoomForm(p => ({ ...p, is_shared: e.target.checked }))} />
                <span>Shared</span>
              </label>
              <label className="infra-checkbox-label">
                <input type="checkbox" checked={roomForm.is_active}
                  onChange={e => setRoomForm(p => ({ ...p, is_active: e.target.checked }))} />
                <span>Active</span>
              </label>
            </div>
            <div className="sec-form-actions">
              <button type="submit" className="sec-submit-btn" disabled={submittingRoom}>
                {submittingRoom ? "Saving…" : editRoomId ? "Update Room" : "Add Room"}
              </button>
              <button type="button" className="sec-cancel-btn" onClick={cancelRoomEdit}>Cancel</button>
            </div>
          </form>
        </div>
      )}

      {/* ── Bulk Upload ── */}
      <div className="data-card" style={{ marginBottom: 16 }}>
        <div className="courses-upload-row">
          <div className="courses-upload-col">
            <BulkUploadCard
              title="Upload Buildings"
              endpoint="infrastructure/building/"
              requiredColumns={["name", "code", "floors"]}
              templateFileName="buildings-upload-template.xlsx"
              templateSampleRow={{ name: "Main Block", code: "MB", floors: 5, is_active: true }}
              mapRow={row => ({ name: row.name, code: row.code, floors: toNumber(row.floors, 1), is_active: toBoolean(row.is_active, true) })}
              onUploadComplete={loadData}
            />
          </div>
          <div className="courses-upload-sep"><hr className="courses-hr" /></div>
          <div className="courses-upload-col">
            <BulkUploadCard
              title="Upload Rooms"
              endpoint="infrastructure/room/bulk-upload/"
              useFileUpload
              requiredColumns={["floor", "capacity", "room_type"]}
              templateFileName="rooms-upload-template.xlsx"
              templateSampleRow={{ building_code: "MB", room_number: "A201", floor: 2, capacity: 60, room_type: "THEORY", is_active: true, is_shared: true, priority_weight: 1 }}
              onUploadComplete={loadData}
            />
          </div>
        </div>
      </div>

      {/* ── Summary Strip ── */}
      {!loading && (
        <div className="sec-summary-strip">
          <div className="sec-summary-item">
            <FaBuilding />
            <span><strong>{buildings.length}</strong> Buildings</span>
          </div>
          <div className="sec-summary-item">
            <FaDoorOpen />
            <span><strong>{rooms.length}</strong> Rooms</span>
          </div>
          <div className="sec-summary-item">
            <FaLayerGroup />
            <span><strong>{theoryCount}</strong> Theory</span>
          </div>
          <div className="sec-summary-item">
            <FaFlask />
            <span><strong>{labCount}</strong> Labs</span>
          </div>
          <div className="sec-summary-item">
            <FaCheckCircle style={{ color: "var(--success)" }} />
            <span><strong>{totalCap.toLocaleString()}</strong> Total Seats</span>
          </div>
          <div style={{ marginLeft: "auto" }}>
            <div className="pdc-search-wrap">
              <FaSearch className="pdc-search-icon" />
              <input
                className="input pdc-search-input"
                placeholder="Search buildings or rooms…"
                value={search}
                onChange={e => setSearch(e.target.value)}
              />
            </div>
          </div>
        </div>
      )}

      {/* ── Hierarchy ── */}
      {loading ? (
        <div className="sec-loading">
          <div className="sec-loading-spinner" />
          Loading infrastructure…
        </div>
      ) : buildings.length === 0 ? (
        <div className="sec-empty">
          <FaBuilding className="sec-empty-icon" />
          <h3>No buildings registered yet</h3>
          <p>Click "Add Building" to register your first building.</p>
        </div>
      ) : (
        <div className="sec-hierarchy">
          {hierarchy.map(b => {
            const isExpanded = !!expandedBuildings[b.id];
            return (
              <div key={b.id} className="sec-program-block">
                {/* Building header */}
                <button className="sec-program-header" onClick={() => toggleBuilding(b.id)}>
                  <div className="sec-program-left">
                    {isExpanded ? <FaChevronDown size={12} /> : <FaChevronRight size={12} />}
                    <div className="sec-program-icon" style={{ background: "rgba(99,102,241,0.1)", color: "var(--brand)" }}>
                      <FaBuilding />
                    </div>
                    <div>
                      <span className="sec-program-name">{b.name}</span>
                      <span className="sec-program-code">{b.code} &nbsp;·&nbsp; {b.num_floors} floor{b.num_floors !== 1 ? "s" : ""}</span>
                    </div>
                  </div>
                  <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                    <div className="sec-program-meta">
                      <span className="sec-meta-badge">{b.bRooms.length} rooms</span>
                      {b.bRooms.filter(r => r.room_type === "LAB").length > 0 && (
                        <span className="sec-meta-badge">{b.bRooms.filter(r => r.room_type === "LAB").length} labs</span>
                      )}
                      {!b.is_active && <span className="sec-meta-badge" style={{ color: "var(--muted)" }}>Inactive</span>}
                    </div>
                    <div className="sec-card-actions" onClick={e => e.stopPropagation()}>
                      <button className="sec-icon-btn" title="Edit" onClick={() => handleBuildingEdit(b)}>
                        <FaEdit />
                      </button>
                      <button className="sec-icon-btn sec-icon-danger" title="Delete" onClick={() => handleBuildingDelete(b.id)}>
                        <FaTrash />
                      </button>
                    </div>
                  </div>
                </button>

                {/* Floor breakdown */}
                {isExpanded && (
                  <div className="sec-years-container">
                    {b.bRooms.length === 0 ? (
                      <div className="infra-no-rooms">No rooms in this building yet.</div>
                    ) : (
                      Object.entries(b.floorMap)
                        .sort(([a], [z]) => Number(a) - Number(z))
                        .map(([floor, floorRooms]) => {
                          const fKey = `${b.id}-${floor}`;
                          const fExp = !!expandedFloors[fKey];
                          const theoryHere = floorRooms.filter(r => r.room_type === "THEORY").length;
                          const labHere    = floorRooms.filter(r => r.room_type === "LAB").length;
                          return (
                            <div key={fKey} className="sec-year-block">
                              <button className="sec-year-header" onClick={() => toggleFloor(fKey)}>
                                {fExp ? <FaChevronDown size={10} /> : <FaChevronRight size={10} />}
                                <span className="infra-floor-icon">🏢</span>
                                <span className="sec-year-label">
                                  {Number(floor) === 0 ? "Ground Floor" : `Floor ${floor}`}
                                </span>
                                <span className="sec-year-sems">
                                  {theoryHere > 0 && `${theoryHere} theory`}
                                  {theoryHere > 0 && labHere > 0 && " · "}
                                  {labHere > 0 && `${labHere} lab`}
                                </span>
                                <span className="sec-year-count">{floorRooms.length} rooms</span>
                              </button>

                              {fExp && (
                                <div className="sec-cards-grid infra-rooms-grid">
                                  {floorRooms
                                    .sort((a, z) => a.room_number.localeCompare(z.room_number))
                                    .map(r => {
                                      const meta = ROOM_TYPE_META[r.room_type] || ROOM_TYPE_META.THEORY;
                                      const RIcon = meta.icon;
                                      const capPct = Math.min(100, Math.round((r.capacity / 120) * 100));
                                      return (
                                        <div key={r.id} className={`sec-card infra-room-card${!r.is_active ? " infra-inactive" : ""}`}>
                                          <div className="sec-card-top">
                                            <div className="sec-card-name-row">
                                              <div className="infra-room-type-icon" style={{ background: meta.bg, color: meta.color }}>
                                                <RIcon />
                                              </div>
                                              <span className="sec-card-name">{r.room_number}</span>
                                              <span className="sec-card-sem-badge" style={{ background: meta.bg, color: meta.color }}>
                                                {meta.label}
                                              </span>
                                            </div>
                                            <div className="sec-card-actions">
                                              <button className="sec-icon-btn" title="Edit" onClick={() => handleRoomEdit(r)}>
                                                <FaEdit />
                                              </button>
                                              <button className="sec-icon-btn sec-icon-danger" title="Delete" onClick={() => handleRoomDelete(r.id)}>
                                                <FaTrash />
                                              </button>
                                            </div>
                                          </div>

                                          <div className="sec-card-details">
                                            <div className="sec-detail-row">
                                              <span className="sec-detail-label">Capacity</span>
                                              <span className="sec-detail-value" style={{ fontWeight: 700 }}>{r.capacity} seats</span>
                                            </div>
                                            <div className="sec-detail-row">
                                              <span className="sec-detail-label">Priority</span>
                                              <span className="sec-detail-value">{r.priority_weight}</span>
                                            </div>
                                            <div className="sec-detail-row">
                                              <span className="sec-detail-label">Shared</span>
                                              <span className="sec-detail-value">{r.is_shared ? "Yes" : "No"}</span>
                                            </div>
                                            <div className="sec-detail-row">
                                              <span className="sec-detail-label">Status</span>
                                              <span className="sec-detail-value" style={{ color: r.is_active ? "var(--success)" : "var(--muted)" }}>
                                                {r.is_active ? "Active" : "Inactive"}
                                              </span>
                                            </div>
                                          </div>

                                          {/* capacity bar */}
                                          <div className="infra-cap-bar-wrap">
                                            <div className="infra-cap-bar">
                                              <div
                                                className="infra-cap-bar-fill"
                                                style={{ width: `${capPct}%`, background: meta.color }}
                                              />
                                            </div>
                                            <span className="infra-cap-label">{capPct}% of 120</span>
                                          </div>
                                        </div>
                                      );
                                    })}
                                </div>
                              )}
                            </div>
                          );
                        })
                    )}
                  </div>
                )}
              </div>
            );
          })}
        </div>
      )}
    </DashboardLayout>
  );
}

export default InfrastructurePage;
