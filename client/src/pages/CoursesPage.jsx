import { useCallback, useEffect, useState } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import BulkUploadCard from "../components/BulkUploadCard";
import { toBoolean, toNumber } from "../utils/spreadsheet";

function CoursesPage() {
  const [courses, setCourses] = useState([]);
  const [form, setForm] = useState({
    code: "",
    name: "",
    course_type: "THEORY",
    min_weekly_lectures: 1,
    max_weekly_lectures: 1,
    priority: 1,
    requires_lab_room: false,
    requires_consecutive_slots: false,
  });

  const loadCourses = useCallback(async () => {
    const response = await api.get("academics/courses/");
    setCourses(response.data);
  }, []);

  useEffect(() => {
    loadCourses();
  }, [loadCourses]);

  const handleManualSubmit = async (event) => {
    event.preventDefault();
    await api.post("academics/courses/", {
      ...form,
      min_weekly_lectures: Number(form.min_weekly_lectures),
      max_weekly_lectures: Number(form.max_weekly_lectures),
      priority: Number(form.priority),
    });
    setForm({
      code: "",
      name: "",
      course_type: "THEORY",
      min_weekly_lectures: 1,
      max_weekly_lectures: 1,
      priority: 1,
      requires_lab_room: false,
      requires_consecutive_slots: false,
    });
    loadCourses();
  };

  return (
    <DashboardLayout>
      <div className="page-head">
        <h1>Course Management</h1>
        <p>Create and bulk import courses aligned to scheduler constraints.</p>
      </div>

      <BulkUploadCard
        title="Upload Courses"
        endpoint="academics/courses/"
        requiredColumns={[
          "code",
          "name",
          "course_type",
          "min_weekly_lectures",
          "max_weekly_lectures",
        ]}
        templateFileName="courses-upload-template.xlsx"
        templateSampleRow={{
          code: "BCA501",
          name: "Advanced Algorithms",
          course_type: "THEORY",
          min_weekly_lectures: 3,
          max_weekly_lectures: 4,
          priority: 2,
          requires_lab_room: false,
          requires_consecutive_slots: false,
        }}
        mapRow={(row) => ({
          code: row.code,
          name: row.name,
          course_type: String(row.course_type || "THEORY").toUpperCase(),
          min_weekly_lectures: toNumber(row.min_weekly_lectures, 1),
          max_weekly_lectures: toNumber(row.max_weekly_lectures, 1),
          priority: toNumber(row.priority, 1),
          requires_lab_room: toBoolean(row.requires_lab_room, false),
          requires_consecutive_slots: toBoolean(row.requires_consecutive_slots, false),
        })}
        onUploadComplete={loadCourses}
      />

      <section className="data-card">
        <h3>Add Course Manually</h3>
        <form className="manual-form" onSubmit={handleManualSubmit}>
          <input
            className="input"
            placeholder="Course Code"
            value={form.code}
            onChange={(e) => setForm((prev) => ({ ...prev, code: e.target.value }))}
            required
          />
          <input
            className="input"
            placeholder="Course Name"
            value={form.name}
            onChange={(e) => setForm((prev) => ({ ...prev, name: e.target.value }))}
            required
          />
          <select
            className="input"
            value={form.course_type}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, course_type: e.target.value }))
            }
          >
            <option value="THEORY">THEORY</option>
            <option value="LAB">LAB</option>
            <option value="ELECTIVE">ELECTIVE</option>
            <option value="VAM">VAM</option>
          </select>
          <input
            className="input"
            type="number"
            min="1"
            placeholder="Min weekly"
            value={form.min_weekly_lectures}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, min_weekly_lectures: e.target.value }))
            }
          />
          <input
            className="input"
            type="number"
            min="1"
            placeholder="Max weekly"
            value={form.max_weekly_lectures}
            onChange={(e) =>
              setForm((prev) => ({ ...prev, max_weekly_lectures: e.target.value }))
            }
          />
          <input
            className="input"
            type="number"
            min="1"
            placeholder="Priority"
            value={form.priority}
            onChange={(e) => setForm((prev) => ({ ...prev, priority: e.target.value }))}
          />
          <label className="checkbox-inline">
            <input
              type="checkbox"
              checked={form.requires_lab_room}
              onChange={(e) =>
                setForm((prev) => ({ ...prev, requires_lab_room: e.target.checked }))
              }
            />
            Requires Lab Room
          </label>
          <label className="checkbox-inline">
            <input
              type="checkbox"
              checked={form.requires_consecutive_slots}
              onChange={(e) =>
                setForm((prev) => ({
                  ...prev,
                  requires_consecutive_slots: e.target.checked,
                }))
              }
            />
            Consecutive Slots
          </label>
          <button type="submit" className="btn-primary">Add Course</button>
        </form>
      </section>

      <section className="data-card">
        <h3>Course List ({courses.length})</h3>
        <div className="table-wrap">
          <table>
            <thead>
              <tr>
                <th>Code</th>
                <th>Name</th>
                <th>Type</th>
                <th>Min/Max Weekly</th>
              </tr>
            </thead>
            <tbody>
              {courses.map((item) => (
                <tr key={item.id}>
                  <td>{item.code}</td>
                  <td>{item.name}</td>
                  <td>{item.course_type}</td>
                  <td>
                    {item.min_weekly_lectures}/{item.max_weekly_lectures}
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>
    </DashboardLayout>
  );
}

export default CoursesPage;
