import { useEffect, useMemo, useState } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";

function asList(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.results)) return data.results;
  return [];
}

function TimetableGeneratorPage() {
  const [departments, setDepartments] = useState([]);
  const [terms, setTerms] = useState([]);
  const [programs, setPrograms] = useState([]);
  const [timetables, setTimetables] = useState([]);
  const [selectedDepartmentId, setSelectedDepartmentId] = useState("");
  const [selectedProgramId, setSelectedProgramId] = useState("");
  const [selectedYear, setSelectedYear] = useState("");
  const [selectedSemester, setSelectedSemester] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState(null);
  const [error, setError] = useState("");

  useEffect(() => {
    const load = async () => {
      const [departmentsResp, termsResp, programsResp, timetableResp] = await Promise.all([
        api.get("academics/departments/"),
        api.get("academics/terms/"),
        api.get("academics/programs/"),
        api.get("scheduler/timetables/", {
          params: { ordering: "-created_at" },
        }),
      ]);

      const departmentList = asList(departmentsResp.data);
      const termList = asList(termsResp.data);
      const programList = asList(programsResp.data);

      setDepartments(departmentList);
      setTerms(termList);
      setPrograms(programList);
      setTimetables(asList(timetableResp.data));

      if (departmentList.length) {
        const defaultDepartmentId = String(departmentList[0].id);
        setSelectedDepartmentId(defaultDepartmentId);

        const defaultPrograms = programList.filter(
          (program) => String(program.department) === defaultDepartmentId
        );
        const defaultProgramId = defaultPrograms.length
          ? String(defaultPrograms[0].id)
          : "";
        setSelectedProgramId(defaultProgramId);

        const defaultTerms = termList.filter(
          (term) => String(term.program) === defaultProgramId
        );
        setSelectedYear(defaultTerms.length ? String(defaultTerms[0].year) : "");
        setSelectedSemester(defaultTerms.length ? String(defaultTerms[0].semester) : "");
      }
    };

    load();
  }, []);

  const filteredPrograms = useMemo(() => {
    if (!selectedDepartmentId) return [];
    return programs.filter(
      (program) => String(program.department) === selectedDepartmentId
    );
  }, [programs, selectedDepartmentId]);

  const filteredTerms = useMemo(() => {
    if (!selectedProgramId) return [];
    return terms.filter((term) => String(term.program) === selectedProgramId);
  }, [terms, selectedProgramId]);

  const availableYears = useMemo(() => {
    const unique = [...new Set(filteredTerms.map((term) => String(term.year)))];
    return unique.sort((a, b) => Number(a) - Number(b));
  }, [filteredTerms]);

  const availableSemesters = useMemo(() => {
    if (!selectedYear) return [];
    const unique = [
      ...new Set(
        filteredTerms
          .filter((term) => String(term.year) === selectedYear)
          .map((term) => String(term.semester))
      ),
    ];
    return unique.sort((a, b) => Number(a) - Number(b));
  }, [filteredTerms, selectedYear]);

  const resolvedTermId = useMemo(() => {
    const term = filteredTerms.find(
      (item) =>
        String(item.year) === selectedYear &&
        String(item.semester) === selectedSemester
    );
    return term ? String(term.id) : "";
  }, [filteredTerms, selectedYear, selectedSemester]);

  const handleDepartmentChange = (value) => {
    setSelectedDepartmentId(value);
    setResult(null);
    setError("");

    const nextPrograms = programs.filter(
      (program) => String(program.department) === value
    );
    const nextProgramId = nextPrograms.length ? String(nextPrograms[0].id) : "";
    setSelectedProgramId(nextProgramId);

    const nextTerms = terms.filter((term) => String(term.program) === nextProgramId);
    setSelectedYear(nextTerms.length ? String(nextTerms[0].year) : "");
    setSelectedSemester(nextTerms.length ? String(nextTerms[0].semester) : "");
  };

  const handleProgramChange = (value) => {
    setSelectedProgramId(value);
    setResult(null);
    setError("");

    const nextTerms = terms.filter((term) => String(term.program) === value);
    setSelectedYear(nextTerms.length ? String(nextTerms[0].year) : "");
    setSelectedSemester(nextTerms.length ? String(nextTerms[0].semester) : "");
  };

  const handleYearChange = (value) => {
    setSelectedYear(value);
    setResult(null);
    setError("");

    const semesterValues = filteredTerms
      .filter((term) => String(term.year) === value)
      .map((term) => String(term.semester));
    setSelectedSemester(semesterValues.length ? semesterValues[0] : "");
  };

  const handleGenerate = async () => {
    if (!resolvedTermId) return;
    setLoading(true);
    setError("");
    setResult(null);

    try {
      const response = await api.post("scheduler/generate/", {
        term_id: Number(resolvedTermId),
      });
      setResult(response.data);

      const timetableResp = await api.get("scheduler/timetables/", {
        params: { ordering: "-created_at" },
      });
      setTimetables(asList(timetableResp.data));
    } catch (err) {
      const message = err?.response?.data?.error || err?.message || "Failed to generate timetable.";
      setError(message);
    } finally {
      setLoading(false);
    }
  };

  const termMap = useMemo(() => Object.fromEntries(terms.map((t) => [t.id, t])), [terms]);
  const programMap = useMemo(
    () => Object.fromEntries(programs.map((p) => [p.id, p])),
    [programs]
  );

  const departmentMap = useMemo(
    () => Object.fromEntries(departments.map((d) => [d.id, d])),
    [departments]
  );

  const historyRows = useMemo(() => {
    return timetables.map((tt) => {
      const term = termMap[tt.term];
      const program = programMap[term?.program];
      const department = departmentMap[program?.department];
      const createdAt = tt.created_at ? new Date(tt.created_at) : null;

      return {
        id: tt.id,
        version: tt.version,
        departmentCode: department?.code || "DEP",
        programCode: program?.code || "PRG",
        programName: program?.name || "Unknown Program",
        year: term?.year || "-",
        semester: term?.semester || "-",
        createdDate: createdAt
          ? createdAt.toLocaleDateString("en-IN", {
              day: "2-digit",
              month: "short",
              year: "numeric",
            })
          : "-",
        createdTime: createdAt
          ? createdAt.toLocaleTimeString("en-IN", {
              hour: "2-digit",
              minute: "2-digit",
            })
          : "-",
      };
    });
  }, [timetables, termMap, programMap, departmentMap]);

  return (
    <DashboardLayout>
      <div className="page-head">
        <h1>Timetable Generator</h1>
        <p>Configure generation parameters and create constraint-aware academic timetables.</p>
      </div>

      <div className="generator-grid">
        <section className="data-card generator-params-card">
          <h3>Generation Parameters</h3>

          <div className="generator-fields">
            <label className="generator-label">Department / School *</label>
            <select
              className="input"
              value={selectedDepartmentId}
              onChange={(e) => handleDepartmentChange(e.target.value)}
            >
              <option value="">Select department</option>
              {departments.map((department) => (
                <option key={department.id} value={department.id}>
                  {department.code} - {department.name}
                </option>
              ))}
            </select>
          </div>

          <div className="generator-fields">
            <label className="generator-label">Program *</label>
            <select
              className="input"
              value={selectedProgramId}
              onChange={(e) => handleProgramChange(e.target.value)}
            >
              <option value="">Select program</option>
              {filteredPrograms.map((program) => (
                <option key={program.id} value={program.id}>
                  {program.code} - {program.name}
                </option>
              ))}
            </select>
          </div>

          <div className="generator-fields">
            <label className="generator-label">Year *</label>
            <select
              className="input"
              value={selectedYear}
              onChange={(e) => handleYearChange(e.target.value)}
            >
              <option value="">Select year</option>
              {availableYears.map((year) => (
                <option key={year} value={year}>
                  Year {year}
                </option>
              ))}
            </select>
          </div>

          <div className="generator-fields">
            <label className="generator-label">Semester *</label>
            <select
              className="input"
              value={selectedSemester}
              onChange={(e) => setSelectedSemester(e.target.value)}
            >
              <option value="">Select semester</option>
              {availableSemesters.map((semester) => (
                <option key={semester} value={semester}>
                  Semester {semester}
                </option>
              ))}
            </select>
          </div>

          {!resolvedTermId ? (
            <p className="upload-help">No academic term exists for this Program/Year/Semester selection.</p>
          ) : null}

          <button
            type="button"
            className="btn-primary generator-btn"
            onClick={handleGenerate}
            disabled={!resolvedTermId || loading}
          >
            {loading ? "Generating..." : "Generate Baseline Timetable"}
          </button>

          {error ? <p className="upload-error generator-error">{error}</p> : null}

          {result ? (
            <div className="generator-result">
              <div><span>Status</span><strong>{result.status}</strong></div>
              <div><span>Allocations</span><strong>{result.allocations ?? 0}</strong></div>
              <div><span>Avg Score</span><strong>{result.avg_score ?? 0}</strong></div>
              <div><span>ML Used</span><strong>{String(result.ml_used)}</strong></div>
            </div>
          ) : null}
        </section>

        <section className="data-card generator-history-card">
          <h3>Generation History</h3>
          <p className="upload-help">Programs and terms for previously generated timetables.</p>

          {historyRows.length ? (
            <div className="history-list">
              {historyRows.map((item) => (
                <article key={item.id} className="history-item">
                  <div className="history-main">
                    <h4>{item.departmentCode} / {item.programCode} - Year {item.year} Sem {item.semester}</h4>
                    <p>{item.programName}</p>
                  </div>
                  <div className="history-meta">
                    <small>{item.createdDate} {item.createdTime}</small>
                    <span>V{item.version}</span>
                  </div>
                </article>
              ))}
            </div>
          ) : (
            <p className="upload-help">No generation history yet. Generate your first timetable.</p>
          )}
        </section>
      </div>

      {result && Array.isArray(result.unscheduled) && result.unscheduled.length ? (
        <section className="data-card">
          <h3>Unscheduled Items</h3>
          <div className="upload-partial">
            <ul>
              {result.unscheduled.map((item) => (
                <li key={item}>{item}</li>
              ))}
            </ul>
          </div>
        </section>
      ) : null}
    </DashboardLayout>
  );
}

export default TimetableGeneratorPage;
