import { useCallback, useEffect, useState } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import BulkUploadCard from "../components/BulkUploadCard";
import { toBoolean, toNumber } from "../utils/spreadsheet";
import { asList, extractError } from "../utils/helpers";
import {
  FaChevronDown,
  FaChevronUp,
  FaTrash,
  FaEdit,
  FaUserTie,
} from "react-icons/fa";

const DAYS = [
  { key: "MON", label: "Monday" },
  { key: "TUE", label: "Tuesday" },
  { key: "WED", label: "Wednesday" },
  { key: "THU", label: "Thursday" },
  { key: "FRI", label: "Friday" },
];

const SLOTS = [1, 2, 3, 4, 5, 6];

const SLOT_TIMES = {
  1: "09:40 – 10:35",
  2: "10:35 – 11:30",
  3: "11:30 – 12:25",
  4: "12:25 – 13:20",
  5: "14:15 – 15:10",
  6: "15:10 – 16:05",
};

const INITIAL_FORM = {
  name: "",
  employee_id: "",
  role: "REGULAR",
  max_lectures_per_day: 4,
  department: "",
};

function buildInitialAvailability() {
  const avail = {};
  DAYS.forEach((d) => {
    avail[d.key] = { allDay: true, slots: {} };
    SLOTS.forEach((s) => {
      avail[d.key].slots[s] = true;
    });
  });
  return avail;
}

function FacultyPage() {
  const [faculty, setFaculty] = useState([]);
  const [departments, setDepartments] = useState([]);
  const [courses, setCourses] = useState([]);
  const [availabilityData, setAvailabilityData] = useState([]);
  const [eligibilityData, setEligibilityData] = useState([]);
  const [loading, setLoading] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [error, setError] = useState("");
  const [success, setSuccess] = useState("");

  const [form, setForm] = useState(INITIAL_FORM);
  const [showAvailability, setShowAvailability] = useState(false);
  const [availability, setAvailability] = useState(buildInitialAvailability());
  const [selectedSubjects, setSelectedSubjects] = useState({});

  const loadAll = useCallback(async () => {
    try {
      setLoading(true);
      const [facResp, deptResp, courseResp, availResp, eligResp] =
        await Promise.all([
          api.get("faculty/faculty/").catch(() => null),
          api.get("academics/departments/").catch(() => null),
          api.get("academics/courses/").catch(() => null),
          api.get("faculty/teacher-availability/").catch(() => null),
          api.get("faculty/faculty-subject-eligibility/").catch(() => null),
        ]);

      setFaculty(facResp ? asList(facResp.data) : []);
      setDepartments(deptResp ? asList(deptResp.data) : []);
      setCourses(courseResp ? asList(courseResp.data) : []);
      setAvailabilityData(availResp ? asList(availResp.data) : []);
      setEligibilityData(eligResp ? asList(eligResp.data) : []);
    } catch (err) {
      console.error("Failed to load data:", err);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadAll();
  }, [loadAll]);

  const toggleAllDay = (dayKey) => {
    setAvailability((prev) => {
      const day = prev[dayKey];
      const newAllDay = !day.allDay;
      const newSlots = {};
      SLOTS.forEach((s) => {
        newSlots[s] = newAllDay;
      });
      return { ...prev, [dayKey]: { allDay: newAllDay, slots: newSlots } };
    });
  };

  const toggleSlot = (dayKey, slot) => {
    setAvailability((prev) => {
      const day = prev[dayKey];
      const newSlots = { ...day.slots, [slot]: !day.slots[slot] };
      const allChecked = SLOTS.every((s) => newSlots[s]);
      return {
        ...prev,
        [dayKey]: { allDay: allChecked, slots: newSlots },
      };
    });
  };

  const toggleSubject = (courseId) => {
    setSelectedSubjects((prev) => {
      const copy = { ...prev };
      if (copy[courseId]) {
        delete copy[courseId];
      } else {
        copy[courseId] = true;
      }
      return copy;
    });
  };

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError("");
    setSuccess("");
    setSubmitting(true);

    try {
      // 1. Create faculty
      const facPayload = {
        name: form.name,
        employee_id: form.employee_id,
        role: form.role,
        max_lectures_per_day: Number(form.max_lectures_per_day),
        max_consecutive_lectures: 2,
        max_weekly_load: 18,
        is_active: true,
      };
      if (form.department) {
        facPayload.department = Number(form.department);
      }

      const facResp = await api.post("faculty/faculty/", facPayload);
      const facultyId = facResp.data.id;

      // 2. Create availability entries
      const availPromises = [];
      DAYS.forEach((d) => {
        const dayData = availability[d.key];
        const activeSlots = SLOTS.filter((s) => dayData.slots[s]);
        if (activeSlots.length === 0) return;

        // Group consecutive slots into blocks
        let blockStart = activeSlots[0];
        let blockEnd = activeSlots[0];

        for (let i = 1; i < activeSlots.length; i++) {
          if (activeSlots[i] === blockEnd + 1) {
            blockEnd = activeSlots[i];
          } else {
            availPromises.push(
              api.post("faculty/teacher-availability/", {
                faculty: facultyId,
                day: d.key,
                start_slot: blockStart,
                end_slot: blockEnd + 1,
              })
            );
            blockStart = activeSlots[i];
            blockEnd = activeSlots[i];
          }
        }
        availPromises.push(
          api.post("faculty/teacher-availability/", {
            faculty: facultyId,
            day: d.key,
            start_slot: blockStart,
            end_slot: blockEnd + 1,
          })
        );
      });

      await Promise.all(availPromises);

      // 3. Create subject eligibility entries
      const subjectIds = Object.keys(selectedSubjects).filter(
        (id) => selectedSubjects[id]
      );
      if (subjectIds.length > 0) {
        await Promise.all(
          subjectIds.map((courseId) =>
            api.post("faculty/faculty-subject-eligibility/", {
              faculty: facultyId,
              course: Number(courseId),
              priority_weight: 1,
            })
          )
        );
      }

      // Reset form
      setForm(INITIAL_FORM);
      setAvailability(buildInitialAvailability());
      setSelectedSubjects({});
      setShowAvailability(false);
      setSuccess("Faculty member registered successfully.");
      loadAll();
    } catch (err) {
      setError(extractError(err, "Failed to register faculty."));
    } finally {
      setSubmitting(false);
    }
  };

  const handleDelete = async (id) => {
    try {
      await api.delete(`faculty/faculty/${id}/`);
      loadAll();
    } catch (err) {
      setError(extractError(err, "Failed to delete faculty."));
    }
  };

  // Build lookup maps for display
  const availByFaculty = {};
  availabilityData.forEach((a) => {
    if (!availByFaculty[a.faculty]) availByFaculty[a.faculty] = [];
    availByFaculty[a.faculty].push(a);
  });

  const eligByFaculty = {};
  eligibilityData.forEach((e) => {
    if (!eligByFaculty[e.faculty]) eligByFaculty[e.faculty] = [];
    eligByFaculty[e.faculty].push(e);
  });

  const courseMap = {};
  courses.forEach((c) => {
    courseMap[c.id] = c;
  });

  const formatAvailability = (facId) => {
    const items = availByFaculty[facId];
    if (!items || items.length === 0) return "Not set";
    const daySlots = {};
    items.forEach((a) => {
      if (!daySlots[a.day]) daySlots[a.day] = [];
      for (let s = a.start_slot; s < a.end_slot; s++) {
        daySlots[a.day].push(s);
      }
    });
    return Object.entries(daySlots)
      .map(([day, slots]) => `${day}: ${slots.sort().join(",")}`)
      .join(" | ");
  };

  const getSubjectTags = (facId) => {
    const items = eligByFaculty[facId];
    if (!items || items.length === 0) return [];
    return items.map((e) => {
      const course = courseMap[e.course];
      return course ? course.code : `#${e.course}`;
    });
  };

  return (
    <DashboardLayout>
      <div className="page-head">
        <h1>Faculty Management</h1>
        <p>Register faculty members with availability and subject eligibility.</p>
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
        onUploadComplete={loadAll}
      />

      <div className="faculty-two-col">
        {/* ── LEFT: Register Form ── */}
        <section className="data-card faculty-form-card">
          <h3>
            <FaUserTie style={{ marginRight: 8, color: "var(--brand)" }} />
            Register Faculty
          </h3>

          {error && <p className="upload-error">{error}</p>}
          {success && <p className="upload-success">{success}</p>}

          <form className="faculty-register-form" onSubmit={handleSubmit}>
            {/* Name */}
            <div className="form-group">
              <label className="form-label">Faculty Name</label>
              <input
                className="input"
                placeholder="e.g. Dr. John Doe"
                value={form.name}
                onChange={(e) =>
                  setForm((p) => ({ ...p, name: e.target.value }))
                }
                required
              />
            </div>

            {/* Employee ID */}
            <div className="form-group">
              <label className="form-label">Employee ID</label>
              <input
                className="input"
                placeholder="e.g. FAC1001"
                value={form.employee_id}
                onChange={(e) =>
                  setForm((p) => ({ ...p, employee_id: e.target.value }))
                }
                required
              />
            </div>

            {/* Role dropdown */}
            <div className="form-group">
              <label className="form-label">Role</label>
              <select
                className="input"
                value={form.role}
                onChange={(e) =>
                  setForm((p) => ({ ...p, role: e.target.value }))
                }
              >
                <option value="DEAN">Dean</option>
                <option value="HOD">Head of Department</option>
                <option value="SENIOR">Senior Faculty</option>
                <option value="REGULAR">Regular Faculty</option>
                <option value="VISITING">Visiting Faculty</option>
              </select>
            </div>

            {/* Max Lectures / Day dropdown */}
            <div className="form-group">
              <label className="form-label">Max Lectures / Day</label>
              <select
                className="input"
                value={form.max_lectures_per_day}
                onChange={(e) =>
                  setForm((p) => ({
                    ...p,
                    max_lectures_per_day: e.target.value,
                  }))
                }
              >
                {[1, 2, 3, 4, 5, 6].map((n) => (
                  <option key={n} value={n}>
                    {n} lecture{n > 1 ? "s" : ""}
                  </option>
                ))}
              </select>
            </div>

            {/* Department dropdown */}
            <div className="form-group">
              <label className="form-label">Department</label>
              <select
                className="input"
                value={form.department}
                onChange={(e) =>
                  setForm((p) => ({ ...p, department: e.target.value }))
                }
              >
                <option value="">— Select Department —</option>
                {departments.map((d) => (
                  <option key={d.id} value={d.id}>
                    {d.name}
                  </option>
                ))}
              </select>
            </div>

            {/* ── Availability Config ── */}
            <div className="form-group">
              <button
                type="button"
                className="avail-toggle-btn"
                onClick={() => setShowAvailability((v) => !v)}
              >
                <span>Configure Availability</span>
                {showAvailability ? <FaChevronUp /> : <FaChevronDown />}
              </button>
            </div>

            {showAvailability && (
              <div className="avail-config">
                {DAYS.map((d) => (
                  <div key={d.key} className="avail-day-row">
                    <div className="avail-day-header">
                      <span className="avail-day-label">{d.label}</span>
                      <label className="avail-allday-check">
                        <input
                          type="checkbox"
                          checked={availability[d.key].allDay}
                          onChange={() => toggleAllDay(d.key)}
                        />
                        <span>Available all day</span>
                      </label>
                    </div>
                    <div className="avail-slots-row">
                      {SLOTS.map((s) => (
                        <label
                          key={s}
                          className={`avail-slot-chip ${
                            availability[d.key].slots[s] ? "active" : ""
                          }`}
                          title={SLOT_TIMES[s]}
                        >
                          <input
                            type="checkbox"
                            checked={availability[d.key].slots[s]}
                            onChange={() => toggleSlot(d.key, s)}
                          />
                          Slot {s}
                        </label>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}

            {/* ── Subject Eligibility ── */}
            <div className="form-group">
              <label className="form-label">Subject Eligibility</label>
              {courses.length === 0 ? (
                <p className="upload-help" style={{ margin: 0 }}>
                  No courses registered yet.
                </p>
              ) : (
                <div className="subject-grid">
                  {courses.map((c) => (
                    <label
                      key={c.id}
                      className={`subject-chip ${
                        selectedSubjects[c.id] ? "active" : ""
                      }`}
                    >
                      <input
                        type="checkbox"
                        checked={!!selectedSubjects[c.id]}
                        onChange={() => toggleSubject(c.id)}
                      />
                      {c.code} – {c.name}
                    </label>
                  ))}
                </div>
              )}
            </div>

            <div className="form-group form-group-btn">
              <button
                type="submit"
                className="btn-primary"
                disabled={submitting}
              >
                {submitting ? "Registering..." : "Register Faculty"}
              </button>
            </div>
          </form>
        </section>

        {/* ── RIGHT: Faculty List ── */}
        <section className="data-card faculty-list-card">
          <h3>Faculty List ({faculty.length})</h3>
          {loading ? (
            <p className="upload-help">Loading faculty data...</p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Name</th>
                    <th>Role</th>
                    <th>Max/Day</th>
                    <th>Availability</th>
                    <th>Subjects</th>
                    <th>Actions</th>
                  </tr>
                </thead>
                <tbody>
                  {faculty.length === 0 ? (
                    <tr>
                      <td
                        colSpan="6"
                        style={{
                          textAlign: "center",
                          color: "var(--muted)",
                          padding: 24,
                        }}
                      >
                        No faculty records yet.
                      </td>
                    </tr>
                  ) : (
                    faculty.map((f) => {
                      const tags = getSubjectTags(f.id);
                      return (
                        <tr key={f.id}>
                          <td>
                            <div className="fac-name-cell">
                              <div className="fac-avatar">
                                {f.name.charAt(0).toUpperCase()}
                              </div>
                              <div>
                                <div className="fac-name">{f.name}</div>
                                <div className="fac-emp-id">
                                  {f.employee_id}
                                </div>
                              </div>
                            </div>
                          </td>
                          <td>
                            <span
                              className={`role-badge role-${f.role.toLowerCase()}`}
                            >
                              {f.role}
                            </span>
                          </td>
                          <td>{f.max_lectures_per_day}</td>
                          <td>
                            <span className="avail-summary">
                              {formatAvailability(f.id)}
                            </span>
                          </td>
                          <td>
                            <div className="subject-tags">
                              {tags.length > 0
                                ? tags.map((t) => (
                                    <span key={t} className="subject-tag">
                                      {t}
                                    </span>
                                  ))
                                : "—"}
                            </div>
                          </td>
                          <td>
                            <button
                              className="icon-btn danger"
                              title="Delete"
                              onClick={() => handleDelete(f.id)}
                            >
                              <FaTrash />
                            </button>
                          </td>
                        </tr>
                      );
                    })
                  )}
                </tbody>
              </table>
            </div>
          )}
        </section>
      </div>
    </DashboardLayout>
  );
}

export default FacultyPage;
