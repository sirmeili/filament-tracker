// The npm audit policy: every advisory fails CI except the exceptions the owner approved
// (AGENTS.md section 5). Each exception names the advisory and the highest severity
// accepted, so CI fails again if the advisory is raised.

/** @type {Record<string, { severity: string, reason: string }>} */
export const APPROVED = {
  // deepmerge, via @sveltejs/vite-plugin-svelte (required by SvelteKit). Approved 2026-11-05.
  "GHSA-gcqx-w48m-w2h4": {
    severity: "low",
    reason: "build-time only, merges our own config; never shipped to browsers",
  },
};

/** @type {Record<string, number>} */
const RANK = { info: 0, low: 1, moderate: 2, high: 3, critical: 4 };

/**
 * The advisories in an `npm audit --json` report that are not approved.
 * @param {{ vulnerabilities?: Record<string, { via: Array<unknown> }> }} report
 * @returns {string[]}
 */
export function unapproved(report) {
  const problems = new Set();
  for (const [name, vulnerability] of Object.entries(report.vulnerabilities ?? {})) {
    for (const via of vulnerability.via) {
      if (!via || typeof via !== "object") continue; // depends on another vulnerable package
      const { url = "", title = "", severity = "critical" } = /** @type {any} */ (via);
      const approved = APPROVED[String(url).split("/").pop() ?? ""];
      if (!approved || (RANK[severity] ?? 4) > (RANK[approved.severity] ?? 0)) {
        problems.add(`${name}: ${title} (${severity}) ${url}`);
      }
    }
  }
  return [...problems];
}
