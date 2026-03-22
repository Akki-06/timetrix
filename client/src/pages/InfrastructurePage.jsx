import { useCallback, useEffect, useMemo, useState } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import BulkUploadCard from "../components/BulkUploadCard";
import { toBoolean, toNumber } from "../utils/spreadsheet";
import { asList, extractError } from "../utils/helpers";

function InfrastructurePage() {
  const [buildings, setBuildings] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [loading, setLoading] = useState(true);
  const [buildingError, setBuildingError] = useState("");
  const [buildingSuccess, setBuildingSuccess] = useState("");
  const [roomError, setRoomError] = useState("");
  const [roomSuccess, setRoomSuccess] = useState("");
  const [submittingBuilding, setSubmittingBuilding] = useState(false);
  const [submittingRoom, setSubmittingRoom] = useState(false);

  const [buildingForm, setBuildingForm] = useState({
    name: "",
    code: "",
    floors: 1,
    is_active: true,
  });
  const [roomForm, setRoomForm] = useState({
    building: "",
    room_number: "",
    floor: 1,
    capacity: 40,
    room_type: "THEORY",
    is_active: true,
    is_shared: true,
    priority_weight: 1,
  });

  const loadData = useCallback(async () => {
    try {
      setLoading(true);
      const [buildingsResponse, roomsResponse] = await Promise.all([
        api.get("infrastructure/building/"),
        api.get("infrastructure/room/"),
      ]);
      setBuildings(asList(buildingsResponse.data));
      setRooms(asList(roomsResponse.data));
    } catch (err) {
      console.error("Failed to load infrastructure:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadData();
  }, [loadData]);

  const buildingCodeToId = useMemo(() => {
    const map = {};
    buildings.forEach((building) => {
      map[String(building.code).trim().toUpperCase()] = building.id;
    });
    return map;
  }, [buildings]);

  const handleBuildingSubmit = async (event) => {
    event.preventDefault();
    setBuildingError("");
    setBuildingSuccess("");
    setSubmittingBuilding(true);

    try {
      await api.post("infrastructure/building/", {
        ...buildingForm,
        floors: Number(buildingForm.floors),
      });
      setBuildingForm({ name: "", code: "", floors: 1, is_active: true });
      setBuildingSuccess("Building added successfully.");
      loadData();
    } catch (err) {
      setBuildingError(extractError(err, "Failed to add building."));
    } finally {
      setSubmittingBuilding(false);
    }
  };

  const handleRoomSubmit = async (event) => {
    event.preventDefault();
    setRoomError("");
    setRoomSuccess("");
    setSubmittingRoom(true);

    try {
      await api.post("infrastructure/room/", {
        ...roomForm,
        building: Number(roomForm.building),
        floor: Number(roomForm.floor),
        capacity: Number(roomForm.capacity),
        priority_weight: Number(roomForm.priority_weight),
      });
      setRoomForm({
        building: "",
        room_number: "",
        floor: 1,
        capacity: 40,
        room_type: "THEORY",
        is_active: true,
        is_shared: true,
        priority_weight: 1,
      });
      setRoomSuccess("Room added successfully.");
      loadData();
    } catch (err) {
      setRoomError(extractError(err, "Failed to add room."));
    } finally {
      setSubmittingRoom(false);
    }
  };

  return (
    <DashboardLayout>
      <div className="page-head">
        <h1>Infrastructure Management</h1>
        <p>Manage buildings and rooms for timetable scheduling.</p>
      </div>

      <div className="upload-grid">
        <BulkUploadCard
          title="Upload Buildings"
          endpoint="infrastructure/building/"
          requiredColumns={["name", "code", "floors"]}
          templateFileName="buildings-upload-template.xlsx"
          templateSampleRow={{
            name: "Main Block",
            code: "MB",
            floors: 5,
            is_active: true,
          }}
          mapRow={(row) => ({
            name: row.name,
            code: row.code,
            floors: toNumber(row.floors, 1),
            is_active: toBoolean(row.is_active, true),
          })}
          onUploadComplete={loadData}
        />

        <BulkUploadCard
          title="Upload Rooms"
          endpoint="infrastructure/room/"
          requiredColumns={["building_code", "room_number", "floor", "capacity", "room_type"]}
          helperText="building_code must match an existing building code."
          templateFileName="rooms-upload-template.xlsx"
          templateSampleRow={{
            building_code: "MB",
            room_number: "A201",
            floor: 2,
            capacity: 60,
            room_type: "THEORY",
            is_active: true,
            is_shared: true,
            priority_weight: 1,
          }}
          mapRow={(row, lineNumber) => {
            const buildingCode = String(row.building_code || "")
              .trim()
              .toUpperCase();
            const buildingId = buildingCodeToId[buildingCode];

            if (!buildingId) {
              throw new Error(
                `Unknown building_code '${buildingCode}' at row ${lineNumber}`
              );
            }

            return {
              building: buildingId,
              room_number: row.room_number,
              floor: toNumber(row.floor, 1),
              capacity: toNumber(row.capacity, 40),
              room_type: String(row.room_type || "THEORY").toUpperCase(),
              is_active: toBoolean(row.is_active, true),
              is_shared: toBoolean(row.is_shared, true),
              priority_weight: toNumber(row.priority_weight, 1),
            };
          }}
          onUploadComplete={loadData}
        />
      </div>

      <div className="upload-grid">
        <section className="data-card">
          <h3>Add Building Manually</h3>

          {buildingError && <p className="upload-error">{buildingError}</p>}
          {buildingSuccess && <p className="upload-success">{buildingSuccess}</p>}

          <form className="manual-form" onSubmit={handleBuildingSubmit}>
            <div className="form-group">
              <label className="form-label">Building Name</label>
              <input
                className="input"
                placeholder="e.g. Main Block"
                value={buildingForm.name}
                onChange={(e) =>
                  setBuildingForm((prev) => ({ ...prev, name: e.target.value }))
                }
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Building Code</label>
              <input
                className="input"
                placeholder="e.g. MB"
                value={buildingForm.code}
                onChange={(e) =>
                  setBuildingForm((prev) => ({ ...prev, code: e.target.value }))
                }
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">No. of Floors</label>
              <input
                className="input"
                type="number"
                min="1"
                value={buildingForm.floors}
                onChange={(e) =>
                  setBuildingForm((prev) => ({ ...prev, floors: e.target.value }))
                }
              />
            </div>
            <div className="form-group">
              <label className="checkbox-inline">
                <input
                  type="checkbox"
                  checked={buildingForm.is_active}
                  onChange={(e) =>
                    setBuildingForm((prev) => ({
                      ...prev,
                      is_active: e.target.checked,
                    }))
                  }
                />
                Active
              </label>
            </div>
            <div className="form-group form-group-btn">
              <button type="submit" className="btn-primary" disabled={submittingBuilding}>
                {submittingBuilding ? "Adding..." : "Add Building"}
              </button>
            </div>
          </form>
        </section>

        <section className="data-card">
          <h3>Add Room Manually</h3>

          {roomError && <p className="upload-error">{roomError}</p>}
          {roomSuccess && <p className="upload-success">{roomSuccess}</p>}

          <form className="manual-form" onSubmit={handleRoomSubmit}>
            <div className="form-group">
              <label className="form-label">Building</label>
              <select
                className="input"
                value={roomForm.building}
                onChange={(e) =>
                  setRoomForm((prev) => ({ ...prev, building: e.target.value }))
                }
                required
              >
                <option value="">-- Select Building --</option>
                {buildings.map((building) => (
                  <option key={building.id} value={building.id}>
                    {building.name} ({building.code})
                  </option>
                ))}
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Room Number</label>
              <input
                className="input"
                placeholder="e.g. A201"
                value={roomForm.room_number}
                onChange={(e) =>
                  setRoomForm((prev) => ({ ...prev, room_number: e.target.value }))
                }
                required
              />
            </div>
            <div className="form-group">
              <label className="form-label">Floor</label>
              <input
                className="input"
                type="number"
                min="0"
                value={roomForm.floor}
                onChange={(e) =>
                  setRoomForm((prev) => ({ ...prev, floor: e.target.value }))
                }
              />
            </div>
            <div className="form-group">
              <label className="form-label">Seating Capacity</label>
              <input
                className="input"
                type="number"
                min="1"
                value={roomForm.capacity}
                onChange={(e) =>
                  setRoomForm((prev) => ({ ...prev, capacity: e.target.value }))
                }
              />
            </div>
            <div className="form-group">
              <label className="form-label">Room Type</label>
              <select
                className="input"
                value={roomForm.room_type}
                onChange={(e) =>
                  setRoomForm((prev) => ({ ...prev, room_type: e.target.value }))
                }
              >
                <option value="THEORY">Theory Room</option>
                <option value="LAB">Laboratory</option>
              </select>
            </div>
            <div className="form-group">
              <label className="form-label">Priority Weight</label>
              <input
                className="input"
                type="number"
                min="1"
                max="10"
                value={roomForm.priority_weight}
                onChange={(e) =>
                  setRoomForm((prev) => ({ ...prev, priority_weight: e.target.value }))
                }
              />
            </div>
            <div className="form-group">
              <label className="checkbox-inline">
                <input
                  type="checkbox"
                  checked={roomForm.is_shared}
                  onChange={(e) =>
                    setRoomForm((prev) => ({ ...prev, is_shared: e.target.checked }))
                  }
                />
                Shared Room
              </label>
            </div>
            <div className="form-group">
              <label className="checkbox-inline">
                <input
                  type="checkbox"
                  checked={roomForm.is_active}
                  onChange={(e) =>
                    setRoomForm((prev) => ({ ...prev, is_active: e.target.checked }))
                  }
                />
                Active
              </label>
            </div>
            <div className="form-group form-group-btn">
              <button type="submit" className="btn-primary" disabled={submittingRoom}>
                {submittingRoom ? "Adding..." : "Add Room"}
              </button>
            </div>
          </form>
        </section>
      </div>

      <section className="data-card">
        <h3>Infrastructure Snapshot</h3>
        {loading ? (
          <p className="upload-help">Loading infrastructure data...</p>
        ) : (
          <div className="mini-stats">
            <div>
              <span>Buildings</span>
              <strong>{buildings.length}</strong>
            </div>
            <div>
              <span>Rooms</span>
              <strong>{rooms.length}</strong>
            </div>
            <div>
              <span>Theory Rooms</span>
              <strong>{rooms.filter((r) => r.room_type === "THEORY").length}</strong>
            </div>
            <div>
              <span>Labs</span>
              <strong>{rooms.filter((r) => r.room_type === "LAB").length}</strong>
            </div>
          </div>
        )}
      </section>
    </DashboardLayout>
  );
}

export default InfrastructurePage;
