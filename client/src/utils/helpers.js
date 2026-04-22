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
