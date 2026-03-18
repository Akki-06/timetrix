import { useMemo, useState } from "react";
import DashboardLayout from "../layouts/DashboardLayout";

const defaultSettings = {
  academicYear: "2025-26",
  defaultProgramScope: "department",
  generationMode: "balanced",
  maxLecturesPerDay: 4,
  maxConsecutiveLectures: 2,
  lunchWindow: "12:00-13:00",
  prioritizeSeniorFaculty: true,
  enforceRoomType: true,
  enforceFacultyAvailability: true,
  allowWeekendClasses: false,
  autoPublishGeneratedTimetable: false,
  keepHistoryVersions: 20,
  conflictAlertThreshold: "medium",
  notifyOnGenerationComplete: true,
  notifyOnFailedGeneration: true,
};

function SettingsPage() {
  const [settings, setSettings] = useState(defaultSettings);
  const [savedAt, setSavedAt] = useState("");

  const statCards = useMemo(
    () => [
      {
        label: "Active Rules",
        value: [
          settings.prioritizeSeniorFaculty,
          settings.enforceRoomType,
          settings.enforceFacultyAvailability,
          !settings.allowWeekendClasses,
        ].filter(Boolean).length,
      },
      { label: "History Retention", value: `${settings.keepHistoryVersions} versions` },
      { label: "Conflict Alert", value: settings.conflictAlertThreshold.toUpperCase() },
    ],
    [settings]
  );

  const updateField = (key, value) => {
    setSettings((prev) => ({ ...prev, [key]: value }));
  };

  const handleSave = () => {
    const stamp = new Date().toLocaleString("en-IN", {
      day: "2-digit",
      month: "short",
      year: "numeric",
      hour: "2-digit",
      minute: "2-digit",
    });
    setSavedAt(stamp);
  };

  const handleReset = () => {
    setSettings(defaultSettings);
    setSavedAt("");
  };

  return (
    <DashboardLayout>
      <div className="page-head">
        <h1>Settings</h1>
        <p>Configure timetable behavior, default generation logic, and admin-level controls.</p>
      </div>

      <section className="settings-stats-grid">
        {statCards.map((item) => (
          <article key={item.label} className="settings-stat-card">
            <p>{item.label}</p>
            <strong>{item.value}</strong>
          </article>
        ))}
      </section>

      <section className="settings-grid">
        <article className="data-card settings-card">
          <h3>General Configuration</h3>
          <div className="settings-form-grid">
            <label className="settings-label">
              Academic Year
              <select
                className="input"
                value={settings.academicYear}
                onChange={(e) => updateField("academicYear", e.target.value)}
              >
                <option value="2025-26">2025-26</option>
                <option value="2026-27">2026-27</option>
                <option value="2027-28">2027-28</option>
              </select>
            </label>

            <label className="settings-label">
              Program Scope
              <select
                className="input"
                value={settings.defaultProgramScope}
                onChange={(e) => updateField("defaultProgramScope", e.target.value)}
              >
                <option value="department">Department-wise</option>
                <option value="program">Program-wise</option>
                <option value="campus">Campus-wide</option>
              </select>
            </label>

            <label className="settings-label">
              Generation Mode
              <select
                className="input"
                value={settings.generationMode}
                onChange={(e) => updateField("generationMode", e.target.value)}
              >
                <option value="balanced">Balanced</option>
                <option value="strict">Strict Constraints</option>
                <option value="optimized">Optimized Throughput</option>
              </select>
            </label>

            <label className="settings-label">
              Conflict Alert Threshold
              <select
                className="input"
                value={settings.conflictAlertThreshold}
                onChange={(e) => updateField("conflictAlertThreshold", e.target.value)}
              >
                <option value="low">Low</option>
                <option value="medium">Medium</option>
                <option value="high">High</option>
              </select>
            </label>
          </div>
        </article>

        <article className="data-card settings-card">
          <h3>Scheduling Constraints</h3>
          <div className="settings-form-grid">
            <label className="settings-label">
              Max Lectures Per Day
              <input
                className="input"
                type="number"
                min="1"
                max="8"
                value={settings.maxLecturesPerDay}
                onChange={(e) => updateField("maxLecturesPerDay", Number(e.target.value))}
              />
            </label>

            <label className="settings-label">
              Max Consecutive Lectures
              <input
                className="input"
                type="number"
                min="1"
                max="5"
                value={settings.maxConsecutiveLectures}
                onChange={(e) => updateField("maxConsecutiveLectures", Number(e.target.value))}
              />
            </label>

            <label className="settings-label">
              Lunch Window
              <select
                className="input"
                value={settings.lunchWindow}
                onChange={(e) => updateField("lunchWindow", e.target.value)}
              >
                <option value="12:00-13:00">12:00 PM - 1:00 PM</option>
                <option value="13:00-14:00">1:00 PM - 2:00 PM</option>
              </select>
            </label>

            <label className="settings-label">
              History Retention
              <input
                className="input"
                type="number"
                min="1"
                max="50"
                value={settings.keepHistoryVersions}
                onChange={(e) => updateField("keepHistoryVersions", Number(e.target.value))}
              />
            </label>
          </div>
        </article>

        <article className="data-card settings-card settings-wide-card">
          <h3>Automation and Notifications</h3>
          <div className="settings-toggle-list">
            <label className="settings-toggle-item">
              <div>
                <strong>Prioritize Senior Faculty</strong>
                <p>Assign higher priority in slot allocation for HOD and Senior Faculty.</p>
              </div>
              <input
                type="checkbox"
                checked={settings.prioritizeSeniorFaculty}
                onChange={(e) => updateField("prioritizeSeniorFaculty", e.target.checked)}
              />
            </label>

            <label className="settings-toggle-item">
              <div>
                <strong>Enforce Room Type</strong>
                <p>Ensure LAB courses are mapped only to LAB rooms.</p>
              </div>
              <input
                type="checkbox"
                checked={settings.enforceRoomType}
                onChange={(e) => updateField("enforceRoomType", e.target.checked)}
              />
            </label>

            <label className="settings-toggle-item">
              <div>
                <strong>Enforce Faculty Availability</strong>
                <p>Strictly block scheduling outside faculty availability windows.</p>
              </div>
              <input
                type="checkbox"
                checked={settings.enforceFacultyAvailability}
                onChange={(e) => updateField("enforceFacultyAvailability", e.target.checked)}
              />
            </label>

            <label className="settings-toggle-item">
              <div>
                <strong>Allow Weekend Classes</strong>
                <p>Enable Saturday scheduling for exceptional timetable pressure.</p>
              </div>
              <input
                type="checkbox"
                checked={settings.allowWeekendClasses}
                onChange={(e) => updateField("allowWeekendClasses", e.target.checked)}
              />
            </label>

            <label className="settings-toggle-item">
              <div>
                <strong>Auto-Publish Generated Timetable</strong>
                <p>Immediately publish successful generations to active version.</p>
              </div>
              <input
                type="checkbox"
                checked={settings.autoPublishGeneratedTimetable}
                onChange={(e) => updateField("autoPublishGeneratedTimetable", e.target.checked)}
              />
            </label>

            <label className="settings-toggle-item">
              <div>
                <strong>Notify on Generation Complete</strong>
                <p>Send in-app alert when generation completes successfully.</p>
              </div>
              <input
                type="checkbox"
                checked={settings.notifyOnGenerationComplete}
                onChange={(e) => updateField("notifyOnGenerationComplete", e.target.checked)}
              />
            </label>

            <label className="settings-toggle-item">
              <div>
                <strong>Notify on Generation Failure</strong>
                <p>Send critical alerts when scheduler cannot generate complete output.</p>
              </div>
              <input
                type="checkbox"
                checked={settings.notifyOnFailedGeneration}
                onChange={(e) => updateField("notifyOnFailedGeneration", e.target.checked)}
              />
            </label>
          </div>

          <div className="settings-actions-row">
            <button type="button" className="btn-secondary" onClick={handleReset}>
              Reset to Defaults
            </button>
            <button type="button" className="btn-primary" onClick={handleSave}>
              Save Settings
            </button>
          </div>

          {savedAt ? <p className="upload-success">Settings saved at {savedAt}</p> : null}
        </article>
      </section>

      <section className="data-card">
        <h3>Safety Notes</h3>
        <ul className="settings-note-list">
          <li>Changes in constraints affect future generations only.</li>
          <li>Existing finalized timetables remain unchanged.</li>
          <li>Keep weekend classes disabled unless unavoidable conflict load appears.</li>
        </ul>
      </section>
    </DashboardLayout>
  );
}

export default SettingsPage;
