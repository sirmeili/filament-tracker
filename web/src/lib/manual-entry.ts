/** Checks for the manual entry form (Manual entry in docs/SPEC.md). */

export type ProductChoice = "existing" | "new";

export interface ManualEntry {
  choice: ProductChoice;
  productId: number | null;
  name: string;
  type: string;
  /** "#RRGGBB" from the color input */
  color: string;
  location: string;
  notes: string;
}

export function emptyEntry(): ManualEntry {
  return {
    choice: "existing",
    productId: null,
    name: "",
    type: "",
    color: "#808080",
    location: "",
    notes: "",
  };
}

/** What is missing or wrong, or null. Limits match the server's. */
export function entryProblem(entry: ManualEntry): string | null {
  if (entry.choice === "existing") {
    return entry.productId === null ? "Choose a product." : null;
  }
  if (!entry.name.trim()) return "Enter the product's name.";
  if (entry.name.trim().length > 100) return "Names are at most 100 characters.";
  if (!entry.type.trim()) return "Enter the filament type, such as PLA.";
  if (entry.type.trim().length > 32) return "Types are at most 32 characters.";
  if (!/^#[0-9a-f]{6}$/i.test(entry.color)) return "Choose a color.";
  return null;
}

/** The server's RRGGBBAA color from the "#rrggbb" color input, fully opaque. */
export function rgbaOf(color: string): string {
  return `${color.slice(1).toUpperCase()}FF`;
}

export function blankIsNull(text: string): string | null {
  return text.trim() || null;
}
