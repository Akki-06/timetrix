import { useCallback, useEffect, useState } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import BulkUploadCard from "../components/BulkUploadCard";
import { toBoolean, toNumber } from "../utils/spreadsheet";

function FacultyPage() {
  const [faculty, setFaculty] = useState([]);
  const [form, setForm] = useState({
    name: "",
    employee_id: "",
    role: "REGULAR",
    max_lectures_per_day: 4,
    max_consecutive_lectures: 2,
    max_weekly_load: 18,
  });

  const loadFaculty = useCallback(async () => {
    const response = await api.get("faculty/faculty/");
    setFaculty(response.data);
  }, []);

  useEffect(() => {
    loadFaculty();
  }, [loadFaculty]);

  const handleManualSubmit = async (event) => {
    event.preventDefault();
    await api.post("faculty/faculty/", {
      ...form,
      max_lectures_per_day: Number(form.max_lectures_per_day),
      max_consecutive_lectures: Number(form.max_consecutive_lectures),
      max_weekly_load: Number(form.max_weekly_load),
      is_active: true,
    });

    setForm({
      name: "",
      employee_id: "",
      role: "REGULAR",
      max_lectures_per_day: 4,
      max_consecutive_lectures: 2,
      max_weekly_load: 18,
    });
    loadFaculty();
  };

  return (
    <DashboardLayout>
      <div className="page-head">
        <h1>Faculty Management</h1>
        <p>Manage faculty records and bulk import from Excel/CSV.</p>
      </div>

      <BulkUploadCard
        title="Upload Faculty"
        endpoint="faculty/faculty/"
        requiredColumns={["name", "employee_id"]}
        templateFileName="faculty-upload-template.xlsx"
        templateSampleRow={{
          name: "Dr. John Doe",
          employee_id: "FAC1001",
          role: "REGULAR",
          max_lectures_per_day: 4,
          max_consecutive_lectures: 2,
          max_weekly_load: 18,
          is_active: true,
        }}
        mapRow={(row) => ({
          name: row.name,
          employee_id: row.employee_id,
          role: String(row.role || "REGULAR").toUpperCase(),
          max_lectures_per_day: toNumber(row.max_lectures_per_day, 4),
          max_consecutive_lectures: toNumber(row.max_consecutive_lectures, 2),
          max_weekly_load: toNumber(row.max_weekly_load, 18),
          is_active: toBoolean(row.is_active, true),
        })}
        onUploadComplete={loadFaculty}
      />

      <section className="data-card">
        <h3>Add Faculty Manually</h3>
        <form className="manual-form" onSubmit={handleManualSubmit}>
          <input
            className="input"
            placeholder="Name"
            value={form.name}
            onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
            required
          />
          <input
            className="input"
            placeholder="Employee ID"
            value={form.employee_id}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, employee_id: e.target.value }))
            }
            required
          />
          <select
            className="input"
            value={form.role}
            onChange={(e) => setForm((prev) => ({ ...prev, role: e.target.value }))}
          >
            <option value="DEAN">DEAN</option>
            <option value="HOD">HOD</option>
            <option value="SENIOR">SENIOR</option>
            <option value="REGULAR">REGULAR</option>
            <option value="VISITING">VISITING</option>
          </select>
          <input
            className="input"
            type="number"
            min="1"
            placeholder="Max/day"
            value={form.max_lectures_per_day}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, max_lectures_per_day: e.target.value }))
            }
          />
          <input
            className="input"
            type="number"
            min="1"
            placeholder="Max consecutive"
            value={form.max_consecutive_lectures}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, max_consecutive_lectures: e.target.value }))
            }
          />
          <input
            className="input"
            type="number"
            min="1"
            placeholder="Max weekly"
            value={form.max_weekly_load}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, max_weekly_load: e.target.value }))
            }
          />
          <button type="submit" className="btn-primary">Add Faculty</button>
        </form>
      </section>

      <section className="data-card">
        <h3>Faculty List ({faculty.length})</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Name</th>
                <th>Employee ID</th>
                <th>Role</th>
                <th>Weekly Load</th>
              </tr>
            </thead>
            <tbody>
              {faculty.map((item) => (
                <tr key={item.id}>
                  <td>{item.name}</td>
                  <td>{item.employee_id}</td>
                  <td>{item.role}</td>
                  <td>{item.max_weekly_load}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </DashboardLayout>
  );
}

export default FacultyPage;
