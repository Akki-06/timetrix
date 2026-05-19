/**
 * Normalize API response data — handles both direct arrays and
 * DRF paginated responses { results: [...], count: N }.
 */
export function asList(data) {
  if (Array.isArray(data)) return data;
  if (Array.isArray(data?.results)) return data.results;
  return [];
}

/**
 * Extract a user-friendly error message from an Axios error.
 */
export function extractError(err, fallback = "Something went wrong.") {
  if (!err) return fallback;
  const data = err?.response?.data;
  if (typeof data === "string") return data;
  if (data?.error) return data.error;
  if (data?.detail) return data.detail;
  if (data?.non_field_errors) return data.non_field_errors.join(", ");
  // Collect field-level errors
  if (typeof data === "object" && data !== null) {
    const msgs = Object.entries(data)
      .map(([k, v]) => `${k}: ${Array.isArray(v) ? v.join(", ") : v}`)
      .join(" | ");
    if (msgs) return msgs;
  }
  return err?.message || fallback;
}

/**
 * Strip internal program-disambiguation suffixes from a course code so only
 * the original university code is shown to users.
 *
 * Examples:
 *   "24COA191_BCA"    -> "24COA191"
 *   "24CSE201_BTAIML" -> "24CSE201"
 *   "24LSK101_BCAFSD" -> "24LSK101"
 *   "24CSE671"        -> "24CSE671"   (no suffix — returned as-is)
 *
 * Strips any trailing _ALLCAPS suffix (2+ uppercase letters) automatically.
 */
export function courseDisplayCode(code) {
  if (!code) return code;
  // Strip ALL trailing _PROGRAMCODE suffixes (handles double like _BCA_BCA)
  return code.replace(/(_[A-Z]{2,})+$/, "");
}

/**
 * Format a program object for dropdown / display labels.
 *
 * Returns a clean, human-readable name like:
 *   "BCA"                         — no specialization
 *   "BCA — Cyber Security"        — with specialization
 *   "BTech — AIML"                — with specialization
 *
 * The `display_name` from the API already includes specialization in
 * parentheses (e.g. "BCA (CyberSec)"), and `code` often duplicates it
 * (e.g. "BCA (CyberSec)"), so using `{display_name} ({code})` creates
 * ugly redundant labels. This function avoids that entirely.
 *
 * @param {Object} p — program object with name, specialization, code, display_name
 * @returns {string}
 */
export function formatProgramLabel(p) {
  if (!p) return "";
  const name = p.name || "";
  const spec = p.specialization || "";
  if (spec) return `${name} — ${spec}`;
  return name;
}
