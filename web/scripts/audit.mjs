// Run `npm audit` and fail on any advisory the policy does not approve.

import { execFileSync } from "node:child_process";
import { APPROVED, unapproved } from "./audit-policy.js";

let output;
try {
  // Run as `npm run audit`, npm's own script is known, so no shell is needed on Windows.
  const npm = process.env.npm_execpath;
  output = npm
    ? execFileSync(process.execPath, [npm, "audit", "--json"], { encoding: "utf8" })
    : execFileSync("npm", ["audit", "--json"], { encoding: "utf8" });
} catch (error) {
  // npm audit exits non-zero when it finds anything; the report is still on stdout.
  output = /** @type {{ stdout: string }} */ (error).stdout;
}

const problems = unapproved(JSON.parse(output));
if (problems.length) {
  console.error("Unapproved advisories:\n" + problems.map((p) => `  ${p}`).join("\n"));
  process.exit(1);
}
console.log(
  `npm audit: nothing unapproved (approved exceptions: ${Object.keys(APPROVED).join(", ")})`,
);
