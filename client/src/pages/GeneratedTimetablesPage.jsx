import { useEffect, useMemo, useState } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import { asList } from "../utils/helpers";

const DAYS = ["Monday", "Tuesday", "Wednesday", "Thursday", "Friday"];

const TIME_SLOTS = [
  "09:40-10:35",
  "10:35-11:30",
  "11:30-12:25",
  "12:25-13:20",
  "14:15-15:10",
  "15:10-16:05",
];

const DAY_CODE_TO_NAME = {
  MON: "Monday",
  TUE: "Tuesday",
  WED: "Wednesday",
  THU: "Thursday",
  FRI: "Friday",
};

const SLOT_TO_LABEL = {
  1: "09:40-10:35",
  2: "10:35-11:30",
  3: "11:30-12:25",
  4: "12:25-13:20",
  5: "14:15-15:10",
  6: "15:10-16:05",
};

function lectureColorClass(subject) {
  const s = (subject || "").toLowerCase();
  if (s.includes("data")) return "subject-blue";
  if (s.includes("dbms") || s.includes("database")) return "subject-green";
  if (s.includes("operating")) return "subject-purple";
  if (s.includes("web")) return "subject-cyan";
  if (s.includes("algorithm")) return "subject-orange";
  if (s.includes("network")) return "subject-pink";
  return "subject-gray";
}

function GeneratedTimetablesPage() {
  const [viewMode, setViewMode] = useState("class");

  const [timetables, setTimetables] = useState([]);
  const [allocations, setAllocations] = useState([]);
  const [faculties, setFaculties] = useState([]);
  const [studentGroups, setStudentGroups] = useState([]);
  const [programs, setPrograms] = useState([]);
  const [terms, setTerms] = useState([]);
  const [courses, setCourses] = useState([]);
  const [courseOfferings, setCourseOfferings] = useState([]);
  const [rooms, setRooms] = useState([]);
  const [timeslots, setTimeslots] = useState([]);

  const [selectedTimetable, setSelectedTimetable] = useState("");
  const [selectedProgram, setSelectedProgram] = useState("all");
  const [selectedFaculty, setSelectedFaculty] = useState("all");
  const [selectedStudentGroup, setSelectedStudentGroup] = useState("all");
  const [selectedRoom, setSelectedRoom] = useState("all");

  const [pageLoading, setPageLoading] = useState(true);
  const [allocLoading, setAllocLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    const loadBase = async () => {
      try {
        setPageLoading(true);
        setError("");
        const [
          timetableResp,
          facultyResp,
          groupResp,
          programResp,
          termResp,
          courseResp,
          offeringResp,
          roomResp,
          timeslotResp,
        ] = await Promise.all([
          api.get("scheduler/timetables/"),
          api.get("faculty/faculty/"),
          api.get("academics/student-groups/"),
          api.get("academics/programs/"),
          api.get("academics/terms/"),
          api.get("academics/courses/"),
          api.get("academics/course-offerings/"),
          api.get("infrastructure/room/"),
          api.get("scheduler/timeslots/"),
        ]);

        const tt = asList(timetableResp.data);
        setTimetables(tt);
        setFaculties(asList(facultyResp.data));
        setStudentGroups(asList(groupResp.data));
        setPrograms(asList(programResp.data));
        setTerms(asList(termResp.data));
        setCourses(asList(courseResp.data));
        setCourseOfferings(asList(offeringResp.data));
        setRooms(asList(roomResp.data));
        setTimeslots(asList(timeslotResp.data));

        if (tt.length) setSelectedTimetable(String(tt[0].id));
      } catch (err) {
        console.error("Failed to load timetable data:", err);
        setError("Failed to load data. Please check backend connection.");
      } finally {
        setPageLoading(false);
      }
    };

    loadBase();
  }, []);

  useEffect(() => {
    if (!selectedTimetable) return;

    const loadAllocations = async () => {
      try {
        setAllocLoading(true);
        const response = await api.get("scheduler/allocations/", {
          params: { timetable: selectedTimetable },
        });
        setAllocations(asList(response.data));
      } catch (err) {
        console.error("Failed to load allocations:", err);
        setAllocations([]);
      } finally {
        setAllocLoading(false);
      }
    };

    loadAllocations();
  }, [selectedTimetable]);

  const maps = useMemo(() => {
    return {
      facultyById: Object.fromEntries(faculties.map((f) => [f.id, f])),
      groupById: Object.fromEntries(studentGroups.map((g) => [g.id, g])),
      programById: Object.fromEntries(programs.map((p) => [p.id, p])),
      termById: Object.fromEntries(terms.map((t) => [t.id, t])),
      courseById: Object.fromEntries(courses.map((c) => [c.id, c])),
      offeringById: Object.fromEntries(courseOfferings.map((o) => [o.id, o])),
      roomById: Object.fromEntries(rooms.map((r) => [r.id, r])),
      timeslotById: Object.fromEntries(timeslots.map((t) => [t.id, t])),
    };
  }, [faculties, studentGroups, programs, terms, courses, courseOfferings, rooms, timeslots]);

  const rows = useMemo(() => {
    const enriched = allocations.map((alloc) => {
      const faculty = maps.facultyById[alloc.faculty];
      const group = maps.groupById[alloc.student_group];
      const offering = maps.offeringById[alloc.course_offering];
      const course = maps.courseById[offering?.course];
      const room = maps.roomById[alloc.room];
      const timeslot = maps.timeslotById[alloc.timeslot];
      const term = maps.termById[group?.term];
      const program = maps.programById[term?.program];

      return {
        id: alloc.id,
        facultyId: faculty?.id,
        facultyName: faculty?.name || "-",
        studentGroupId: group?.id,
        studentGroupName: group?.name || "-",
        programId: program?.id,
        programCode: program?.code || "-",
        courseCode: course?.code || "-",
        courseName: course?.name || "-",
        courseType: course?.course_type || "",
        roomId: room?.id,
        roomLabel: room ? `${room.room_number}` : "-",
        roomType: room?.room_type || "",
        dayName: DAY_CODE_TO_NAME[timeslot?.day] || "-",
        slotLabel: SLOT_TO_LABEL[timeslot?.slot_number] || "-",
        rawDay: timeslot?.day,
        rawSlot: timeslot?.slot_number,
      };
    });

    return enriched
      .filter((row) => selectedProgram === "all" || String(row.programId) === selectedProgram)
      .filter((row) => selectedFaculty === "all" || String(row.facultyId) === selectedFaculty)
      .filter((row) => selectedStudentGroup === "all" || String(row.studentGroupId) === selectedStudentGroup)
      .filter((row) => selectedRoom === "all" || String(row.roomId) === selectedRoom);
  }, [allocations, maps, selectedProgram, selectedFaculty, selectedStudentGroup, selectedRoom]);

  const gridData = useMemo(() => {
    const grid = {};
    DAYS.forEach((day) => {
      grid[day] = {};
      TIME_SLOTS.forEach((slot) => {
        grid[day][slot] = null;
      });
    });

    rows.forEach((r) => {
      const day = r.dayName;
      const slot = r.slotLabel;
      if (!grid[day] || grid[day][slot] === undefined) return;
      if (!grid[day][slot]) {
        grid[day][slot] = {
          subject: r.courseName,
          faculty: r.facultyName,
          room: r.roomLabel,
          type: r.roomType === "LAB" || r.courseType === "LAB" ? "lab" : "theory",
        };
      }
    });

    return grid;
  }, [rows]);

  const handleDownloadPdf = () => {
    window.print();
  };

  const hasData = selectedTimetable && allocations.length > 0;

  if (pageLoading) {
    return (
      <DashboardLayout>
        <div className="page-head">
          <h1>Generated Timetables</h1>
          <p className="upload-help">Loading timetable data...</p>
        </div>
      </DashboardLayout>
    );
  }

  if (error) {
    return (
      <DashboardLayout>
        <div className="page-head">
          <h1>Generated Timetables</h1>
          <p className="upload-error">{error}</p>
        </div>
      </DashboardLayout>
    );
  }

  return (
    <DashboardLayout>
      <div className="page-head no-print">
        <h1>Generated Timetables</h1>
        <p>Class-wise, Faculty-wise, Room-wise views with Program/Faculty/Student filters.</p>
      </div>

      <section className="data-card no-print">
        <h3>Filters</h3>
        <div className="manual-form">
          <div className="form-group">
            <label className="form-label">Program</label>
            <select
              className="input"
              value={selectedProgram}
              onChange={(e) => setSelectedProgram(e.target.value)}
            >
              <option value="all">All Programs</option>
              {programs.map((p) => (
                <option key={p.id} value={p.id}>{p.code} - {p.name}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Faculty</label>
            <select
              className="input"
              value={selectedFaculty}
              onChange={(e) => setSelectedFaculty(e.target.value)}
            >
              <option value="all">All Faculty</option>
              {faculties.map((f) => (
                <option key={f.id} value={f.id}>{f.name}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Student Group</label>
            <select
              className="input"
              value={selectedStudentGroup}
              onChange={(e) => setSelectedStudentGroup(e.target.value)}
            >
              <option value="all">All Student Groups</option>
              {studentGroups.map((g) => (
                <option key={g.id} value={g.id}>{g.name}</option>
              ))}
            </select>
          </div>

          <div className="form-group">
            <label className="form-label">Room</label>
            <select
              className="input"
              value={selectedRoom}
              onChange={(e) => setSelectedRoom(e.target.value)}
            >
              <option value="all">All Rooms</option>
              {rooms.map((room) => (
                <option key={room.id} value={room.id}>
                  {room.room_number} ({room.room_type})
                </option>
              ))}
            </select>
          </div>
        </div>
      </section>

      <section className="timetable-card">
        <div className="timetable-top no-print">
          <div>
            <h3>Select Timetable</h3>
            <div className="pill-tabs">
              <button
                type="button"
                className={viewMode === "class" ? "active" : ""}
                onClick={() => setViewMode("class")}
              >
                Class-wise
              </button>
              <button
                type="button"
                className={viewMode === "faculty" ? "active" : ""}
                onClick={() => setViewMode("faculty")}
              >
                Faculty-wise
              </button>
              <button
                type="button"
                className={viewMode === "room" ? "active" : ""}
                onClick={() => setViewMode("room")}
              >
                Room-wise
              </button>
            </div>
          </div>

          <div className="timetable-actions">
            <select
              className="input"
              value={selectedTimetable}
              onChange={(e) => setSelectedTimetable(e.target.value)}
            >
              {timetables.length === 0 && (
                <option value="">No timetables available</option>
              )}
              {timetables.map((tt) => (
                <option key={tt.id} value={tt.id}>
                  Timetable #{tt.id} (V{tt.version})
                </option>
              ))}
            </select>
            <button type="button" className="btn-primary" onClick={handleDownloadPdf}>
              Download PDF
            </button>
          </div>
        </div>

        <div className="view-banner">
          Viewing: {viewMode === "class" ? "Class-wise" : viewMode === "faculty" ? "Faculty-wise" : "Room-wise"}
          {allocLoading && " — Loading..."}
        </div>

        {allocLoading ? (
          <div style={{ padding: "3rem", textAlign: "center", color: "var(--muted)" }}>
            Loading allocations...
          </div>
        ) : !hasData ? (
          <div style={{ padding: "3rem", textAlign: "center", color: "var(--muted)" }}>
            {timetables.length === 0
              ? "No timetables generated yet. Use the Timetable Generator to create one."
              : "Select a timetable to view."}
          </div>
        ) : (
          <div className="timetable-grid-wrap">
            <table className="timetable-grid">
              <thead>
                <tr>
                  <th className="sticky-col">Day / Time</th>
                  {TIME_SLOTS.slice(0, 4).map((slot) => (
                    <th key={slot}>{slot}</th>
                  ))}
                  <th className="lunch-col">13:20-14:15</th>
                  {TIME_SLOTS.slice(4).map((slot) => (
                    <th key={slot}>{slot}</th>
                  ))}
                </tr>
              </thead>
              <tbody>
                {DAYS.map((day) => (
                  <tr key={day}>
                    <td className="sticky-col day-cell">{day}</td>
                    {TIME_SLOTS.slice(0, 4).map((slot) => {
                      const lecture = gridData[day]?.[slot];
                      if (!lecture) {
                        return <td key={slot} className="empty-cell">&mdash;</td>;
                      }
                      return (
                        <td key={slot}>
                          <div className={`lecture-chip ${lectureColorClass(lecture.subject)}`}>
                            <div className="lecture-subject">
                              {lecture.subject}
                              {lecture.type === "lab" ? <span className="lab-tag">Lab</span> : null}
                            </div>
                            <div className="lecture-meta">{lecture.faculty}</div>
                            <div className="lecture-meta">Room: {lecture.room}</div>
                          </div>
                        </td>
                      );
                    })}
                    <td className="lunch-col lunch-cell">LUNCH BREAK</td>
                    {TIME_SLOTS.slice(4).map((slot) => {
                      const lecture = gridData[day]?.[slot];
                      if (!lecture) {
                        return <td key={slot} className="empty-cell">&mdash;</td>;
                      }
                      return (
                        <td key={slot}>
                          <div className={`lecture-chip ${lectureColorClass(lecture.subject)}`}>
                            <div className="lecture-subject">
                              {lecture.subject}
                              {lecture.type === "lab" ? <span className="lab-tag">Lab</span> : null}
                            </div>
                            <div className="lecture-meta">{lecture.faculty}</div>
                            <div className="lecture-meta">Room: {lecture.room}</div>
                          </div>
                        </td>
                      );
                    })}
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        <div className="legend-row no-print">
          <div className="legend-item"><span className="legend-box subject-blue" /> Data Structures</div>
          <div className="legend-item"><span className="legend-box subject-green" /> DBMS</div>
          <div className="legend-item"><span className="legend-box subject-purple" /> Operating Systems</div>
          <div className="legend-item"><span className="legend-box subject-cyan" /> Web Development</div>
          <div className="legend-item"><span className="legend-box lunch-col" /> Lunch Break</div>
        </div>
      </section>
    </DashboardLayout>
  );
}

export default GeneratedTimetablesPage;
