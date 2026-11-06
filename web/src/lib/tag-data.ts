/** The decoded tag fields shown on the Spool detail page. */

export interface TagField {
  label: string;
  value: string;
}

function text(value: unknown, unit = ""): string | null {
  if (value === null || value === undefined || value === "") return null;
  return `${String(value)}${unit}`;
}

/** Material, variant, type, diameter, weight and production date, leaving out any the tag
 * does not have. */
export function tagFields(decoded: Record<string, unknown> | null): TagField[] {
  if (!decoded) return [];
  const produced = typeof decoded.production_date === "string" ? decoded.production_date : null;
  const fields: [string, string | null][] = [
    ["Material", text(decoded.material_id)],
    ["Variant", text(decoded.variant_id)],
    ["Type", text(decoded.detailed_filament_type ?? decoded.filament_type)],
    ["Diameter", text(decoded.filament_diameter_mm, " mm")],
    ["Weight", text(decoded.spool_weight_g, " g")],
    ["Produced", produced ? produced.slice(0, 10) : null],
  ];
  return fields
    .filter((field): field is [string, string] => field[1] !== null)
    .map(([label, value]) => ({ label, value }));
}
