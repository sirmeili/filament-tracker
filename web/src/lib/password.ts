/** Password rules shared by the Account and Users pages (Users and roles in docs/SPEC.md). */

export const MIN_PASSWORD = 12;
export const MAX_PASSWORD = 256;

/** Progress toward the minimum length, 0 to 1, for the meter. */
export function passwordProgress(password: string): number {
  return Math.min(password.length / MIN_PASSWORD, 1);
}

export function passwordMeterText(password: string): string {
  if (password.length === 0) return `At least ${MIN_PASSWORD} characters`;
  if (password.length > MAX_PASSWORD) return `At most ${MAX_PASSWORD} characters`;
  if (password.length < MIN_PASSWORD) {
    const left = MIN_PASSWORD - password.length;
    return `${left} more character${left === 1 ? "" : "s"}`;
  }
  return "Long enough";
}

export function passwordOk(password: string): boolean {
  return password.length >= MIN_PASSWORD && password.length <= MAX_PASSWORD;
}
