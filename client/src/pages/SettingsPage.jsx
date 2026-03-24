import { useCallback, useEffect, useState } from "react";
import DashboardLayout from "../layouts/DashboardLayout";
import api from "../api/axios";
import { asList } from "../utils/helpers";

// ── helpers ──────────────────────────────────────────────────────────────────
function Toggle({ checked, onChange, label, description }) {
  return (
    <label className="settings-toggle-item">
      <div>
        <strong>{label}</strong>
        {description && <p>{description}</p>}
      </div>
      <input type="checkbox" checked={checked} onChange={(e) => onChange(e.target.checked)} />
    </label>
  );
}

function NumInput({ label, value, onChange, min = 1, max = 50, hint }) {
  return (
    <label className="settings-label">
      {label}
      <input
        className="input"
        type="number"
        min={min}
        max={max}
        value={value}
        onChange={(e) => onChange(Number(e.target.value))}
      />
      {hint && <span className="input-hint">{hint}</span>}
    </label>
  );
}

// ── default config ────────────────────────────────────────────────────────────
const DEFAULT_CONFIG = {
  academic_year: "2025-26",
  max_hours_dean: 6,
  max_hours_hod: 12,
  max_hours_regular: 18,
  max_hours_visiting: 8,
  max_lectures_per_day: 4,
  max_consecutive_lectures: 2,
  allow_weekend_classes: false,
  enforce_room_type: true,
  enforce_faculty_availability: true,
  prioritize_senior_faculty: true,
  auto_publish_timetable: false,
  notify_on_generation_complete: true,
  notify_on_failed_generation: true,
  keep_history_versions: 20,
};

function SettingsPage() {
  const [config, setConfig]     = useState(DEFAULT_CONFIG);
  const [slots, setSlots]       = useState([]);
  const [saving, setSaving]     = useState(false);
  const [savingSlots, setSavingSlots] = useState(false);
  const [savedAt, setSavedAt]   = useState("");
  const [error, setError]       = useState("");

  // ── load config + timeslots ──────────────────────────────────────────────
  const loadAll = useCallback(async () => {
    try {
      const [cfgResp, slotResp] = await Promise.all([
        api.get("scheduler/config/").catch(() => null),
        api.get("scheduler/timeslots/").catch(() => null),
      ]);
      if (cfgResp) setConfig(cfgResp.data);
      if (slotResp) {
        // Show only Monday slots (slot definitions are shared across all days)
        const monSlots = asList(slotResp.data)
          .filter((s) => s.day === "MON")
          .sort((a, b) => a.slot_number - b.slot_number);
        setSlots(monSlots);
      }
    } catch (err) {
      console.error("Failed to load settings:", err);
    }
  }, []);

  useEffect(() => { loadAll(); }, [loadAll]);

  // ── save main config ─────────────────────────────────────────────────────
  const handleSaveConfig = async () => {
    setError("");
    setSaving(true);
    try {
      await api.patch("scheduler/config/", config);
      const stamp = new Date().toLocaleString("en-IN", {
        day: "2-digit", month: "short", year: "numeric",
        hour: "2-digit", minute: "2-digit",
      });
      setSavedAt(stamp);
    } catch (err) {
      setError("Failed to save settings. Is the backend running?");
    } finally {
      setSaving(false);
    }
  };

  // ── save timeslot times ──────────────────────────────────────────────────
  const handleSaveSlots = async () => {
    setError("");
    setSavingSlots(true);
    try {
      // Update each slot across all days that share the same slot_number
      for (const slot of slots) {
        // Get all timeslots with this slot_number (all days)
        const allDaySlots = await api.get(
          `scheduler/timeslots/?slot_number=${slot.slot_number}`
        );
        for (const ts of asList(allDaySlots.data)) {
          await api.patch(`scheduler/timeslots/${ts.id}/`, {
            start_time: slot.start_time,
            end_time:   slot.end_time,
            is_lunch:   slot.is_lunch,
          });
        }
      }
      const stamp = new Date().toLocaleString("en-IN", {
        day: "2-digit", month: "short", year: "numeric",
        hour: "2-digit", minute: "2-digit",
      });
      setSavedAt(`Slots saved at ${stamp}`);
    } catch (err) {
      setError("Failed to save time slots.");
    } finally {
      setSavingSlots(false);
    }
  };

  const setSlotField = (idx, field, value) => {
    setSlots((prev) => prev.map((s, i) => i === idx ? { ...s, [field]: value } : s));
  };

  const set = (key, value) => setConfig((prev) => ({ ...prev, [key]: value }));

  return (
    <DashboardLayout>
      <div className="page-head">
        <h1>Settings</h1>
        <p>Configure workloads, time slots, academic year, and scheduling behaviour.</p>
      </div>

      <section className="settings-grid">

        {/* ── 1. ACADEMIC YEAR ─────────────────────────────────────────── */}
        <article className="data-card settings-card">
          <h3>Academic Year</h3>
          <div className="settings-form-grid">
            <label className="settings-label">
              Current Academic Year
              <input
                className="input"
                type="text"
                placeholder="e.g. 2025-26"
                value={config.academic_year}
                onChange={(e) => set("academic_year", e.target.value)}
              />
              <span className="input-hint">
                Used to label all generated timetables and reports
              </span>
            </label>

            <NumInput
              label="Keep History Versions"
              value={config.keep_history_versions}
              onChange={(v) => set("keep_history_versions", v)}
              min={1} max={50}
              hint="Old timetable versions beyond this count are auto-pruned"
            />
          </div>
        </article>

        {/* ── 2. FACULTY WORKLOAD CAPS ──────────────────────────────────── */}
        <article className="data-card settings-card">
          <h3>Faculty Workload Caps (hrs/week)</h3>
          <p className="upload-help" style={{ marginBottom: 12 }}>
            Maximum teaching hours per week by designation. Scheduler enforces these as hard caps.
          </p>
          <div className="settings-form-grid">
            <NumInput label="PVC / Dean"  value={config.max_hours_dean}     onChange={(v) => set("max_hours_dean", v)}     min={1} max={40} />
            <NumInput label="HoD"        value={config.max_hours_hod}      onChange={(v) => set("max_hours_hod", v)}      min={1} max={40} />
            <NumInput label="Regular"    value={config.max_hours_regular}  onChange={(v) => set("max_hours_regular", v)}  min={1} max={40} />
            <NumInput label="Visiting"   value={config.max_hours_visiting} onChange={(v) => set("max_hours_visiting", v)} min={1} max={40} />
          </div>
        </article>

        {/* ── 3. SCHEDULING CONSTRAINTS ─────────────────────────────────── */}
        <article className="data-card settings-card">
          <h3>Scheduling Constraints</h3>
          <div className="settings-form-grid">
            <NumInput
              label="Max Lectures Per Day"
              value={config.max_lectures_per_day}
              onChange={(v) => set("max_lectures_per_day", v)}
              min={1} max={8}
              hint="Per faculty — scheduler blocks any slot that would exceed this"
            />
            <NumInput
              label="Max Consecutive Lectures"
              value={config.max_consecutive_lectures}
              onChange={(v) => set("max_consecutive_lectures", v)}
              min={1} max={5}
              hint="Prevents back-to-back overloading"
            />
          </div>
        </article>

        {/* ── 4. TIME SLOT CONFIGURATION ────────────────────────────────── */}
        <article className="data-card settings-card settings-wide-card">
          <h3>Time Slot Configuration</h3>
          <p className="upload-help" style={{ marginBottom: 12 }}>
            Set start and end times for each slot. Changes apply to all days.
            Mark a slot as Lunch to block it from scheduling.
          </p>

          {slots.length === 0 ? (
            <p className="upload-help">
              No time slots found. Add them via Django admin or seed the DB first.
            </p>
          ) : (
            <div className="table-wrap">
              <table>
                <thead>
                  <tr>
                    <th>Slot</th>
                    <th>Start Time</th>
                    <th>End Time</th>
                    <th>Lunch Break</th>
                  </tr>
                </thead>
                <tbody>
                  {slots.map((slot, idx) => (
                    <tr key={slot.id}>
                      <td><strong>Slot {slot.slot_number}</strong></td>
                      <td>
                        <input
                          type="time"
                          className="input"
                          value={slot.start_time?.slice(0, 5) || ""}
                          onChange={(e) => setSlotField(idx, "start_time", e.target.value + ":00")}
                          style={{ width: 130 }}
                        />
                      </td>
                      <td>
                        <input
                          type="time"
                          className="input"
                          value={slot.end_time?.slice(0, 5) || ""}
                          onChange={(e) => setSlotField(idx, "end_time", e.target.value + ":00")}
                          style={{ width: 130 }}
                        />
                      </td>
                      <td style={{ textAlign: "center" }}>
                        <input
                          type="checkbox"
                          checked={slot.is_lunch}
                          onChange={(e) => setSlotField(idx, "is_lunch", e.target.checked)}
                        />
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          )}

          <div className="settings-actions-row" style={{ marginTop: 16 }}>
            <button
              type="button"
              className="btn-primary"
              onClick={handleSaveSlots}
              disabled={savingSlots || slots.length === 0}
            >
              {savingSlots ? "Saving Slots..." : "Save Time Slots"}
            </button>
          </div>
        </article>

        {/* ── 5. AUTOMATION + CONSTRAINTS ───────────────────────────────── */}
        <article className="data-card settings-card settings-wide-card">
          <h3>Scheduling Behaviour</h3>
          <div className="settings-toggle-list">
            <Toggle
              label="Enforce Faculty Availability"
              description="Block scheduling outside each faculty's declared available slots. Disable to treat all faculty as always available."
              checked={config.enforce_faculty_availability}
              onChange={(v) => set("enforce_faculty_availability", v)}
            />
            <Toggle
              label="Enforce Room Type"
              description="Lab courses (PR) are only assigned to lab rooms. Disable to allow any room."
              checked={config.enforce_room_type}
              onChange={(v) => set("enforce_room_type", v)}
            />
            <Toggle
              label="Prioritize Senior Faculty"
              description="PVC, Dean, and HoD are tried first as candidates for each course."
              checked={config.prioritize_senior_faculty}
              onChange={(v) => set("prioritize_senior_faculty", v)}
            />
            <Toggle
              label="Allow Weekend Classes"
              description="Include Saturday in the scheduling week when load cannot fit Mon–Fri."
              checked={config.allow_weekend_classes}
              onChange={(v) => set("allow_weekend_classes", v)}
            />
            <Toggle
              label="Auto-Publish Generated Timetable"
              description="Immediately mark successful generations as finalized and active."
              checked={config.auto_publish_timetable}
              onChange={(v) => set("auto_publish_timetable", v)}
            />
          </div>
        </article>

        {/* ── 6. NOTIFICATIONS ──────────────────────────────────────────── */}
        <article className="data-card settings-card settings-wide-card">
          <h3>Notifications</h3>
          <div className="settings-toggle-list">
            <Toggle
              label="Notify on Generation Complete"
              description="Show in-app alert when timetable generation succeeds or partially succeeds."
              checked={config.notify_on_generation_complete}
              onChange={(v) => set("notify_on_generation_complete", v)}
            />
            <Toggle
              label="Notify on Generation Failure"
              description="Show critical alert when the scheduler cannot produce any output."
              checked={config.notify_on_failed_generation}
              onChange={(v) => set("notify_on_failed_generation", v)}
            />
          </div>
        </article>

      </section>

      {/* ── SAVE BAR ──────────────────────────────────────────────────────── */}
      <section className="data-card" style={{ marginTop: 0 }}>
        {error   && <p className="upload-error"   style={{ marginBottom: 8 }}>{error}</p>}
        {savedAt && <p className="upload-success" style={{ marginBottom: 8 }}>{savedAt}</p>}

        <div className="settings-actions-row">
          <button
            type="button"
            className="btn-secondary"
            onClick={() => { setConfig(DEFAULT_CONFIG); setSavedAt(""); setError(""); }}
          >
            Reset to Defaults
          </button>
          <button
            type="button"
            className="btn-primary"
            onClick={handleSaveConfig}
            disabled={saving}
          >
            {saving ? "Saving..." : "Save Settings"}
          </button>
        </div>

        <ul className="settings-note-list" style={{ marginTop: 16 }}>
          <li>Workload changes apply to the next generation run — existing timetables are unaffected.</li>
          <li>Time slot changes are reflected immediately in all future timetable views.</li>
          <li>Disabling faculty availability enforcement may cause faculty clashes in practice.</li>
        </ul>
      </section>
    </DashboardLayout>
  );
}

export default SettingsPage;
