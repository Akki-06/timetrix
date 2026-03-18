import { useCallback, useEffect, useMemo, useState } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import BulkUploadCard from "../components/BulkUploadCard";
import { toBoolean, toNumber } from "../utils/spreadsheet";

function InfrastructurePage() {
  const [buildings, setBuildings] = useState([]);
  const [rooms, setRooms] = useState([]);
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
    const [buildingsResponse, roomsResponse] = await Promise.all([
      api.get("infrastructure/building/"),
      api.get("infrastructure/room/"),
    ]);

    setBuildings(buildingsResponse.data);
    setRooms(roomsResponse.data);
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
    await api.post("infrastructure/building/", {
      ...buildingForm,
      floors: Number(buildingForm.floors),
    });
    setBuildingForm({ name: "", code: "", floors: 1, is_active: true });
    loadData();
  };

  const handleRoomSubmit = async (event) => {
    event.preventDefault();
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
    loadData();
  };

  return (
    <DashboardLayout>
      <div className="page-head">
        <h1>Infrastructure Management</h1>
        <p>Upload building and room data from CSV/Excel files.</p>
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
          <form className="manual-form" onSubmit={handleBuildingSubmit}>
            <input
              className="input"
              placeholder="Building Name"
              value={buildingForm.name}
              onChange={(e) =>
                setBuildingForm((prev) => ({ ...prev, name: e.target.value }))
              }
              required
            />
            <input
              className="input"
              placeholder="Building Code"
              value={buildingForm.code}
              onChange={(e) =>
                setBuildingForm((prev) => ({ ...prev, code: e.target.value }))
              }
              required
            />
            <input
              className="input"
              type="number"
              min="1"
              placeholder="Floors"
              value={buildingForm.floors}
              onChange={(e) =>
                setBuildingForm((prev) => ({ ...prev, floors: e.target.value }))
              }
            />
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
            <button type="submit" className="btn-primary">Add Building</button>
          </form>
        </section>

        <section className="data-card">
          <h3>Add Room Manually</h3>
          <form className="manual-form" onSubmit={handleRoomSubmit}>
            <select
              className="input"
              value={roomForm.building}
              onChange={(e) =>
                setRoomForm((prev) => ({ ...prev, building: e.target.value }))
              }
              required
            >
              <option value="">Select Building</option>
              {buildings.map((building) => (
                <option key={building.id} value={building.id}>
                  {building.name} ({building.code})
                </option>
              ))}
            </select>
            <input
              className="input"
              placeholder="Room Number"
              value={roomForm.room_number}
              onChange={(e) =>
                setRoomForm((prev) => ({ ...prev, room_number: e.target.value }))
              }
              required
            />
            <input
              className="input"
              type="number"
              min="0"
              placeholder="Floor"
              value={roomForm.floor}
              onChange={(e) =>
                setRoomForm((prev) => ({ ...prev, floor: e.target.value }))
              }
            />
            <input
              className="input"
              type="number"
              min="1"
              placeholder="Capacity"
              value={roomForm.capacity}
              onChange={(e) =>
                setRoomForm((prev) => ({ ...prev, capacity: e.target.value }))
              }
            />
            <select
              className="input"
              value={roomForm.room_type}
              onChange={(e) =>
                setRoomForm((prev) => ({ ...prev, room_type: e.target.value }))
              }
            >
              <option value="THEORY">THEORY</option>
              <option value="LAB">LAB</option>
            </select>
            <label className="checkbox-inline">
              <input
                type="checkbox"
                checked={roomForm.is_shared}
                onChange={(e) =>
                  setRoomForm((prev) => ({ ...prev, is_shared: e.target.checked }))
                }
              />
              Shared
            </label>
            <button type="submit" className="btn-primary">Add Room</button>
          </form>
        </section>
      </div>

      <section className="data-card">
        <h3>Infrastructure Snapshot</h3>
        <div className="mini-stats">
          <div>
            <span>Buildings</span>
            <strong>{buildings.length}</strong>
          </div>
          <div>
            <span>Rooms</span>
            <strong>{rooms.length}</strong>
          </div>
        </div>
      </section>
    </DashboardLayout>
  );
}

export default InfrastructurePage;
