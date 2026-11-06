/** Wording for Review items. */

import type { EventOut, UnidentifiedTag } from "#lib/api/types.ts";
import { eventTitle } from "#lib/format.ts";

export interface ItemText {
  title: string;
  body: string;
}

/** Why each kind of event gets flagged (Spool states and transitions in docs/SPEC.md). */
const FLAG_REASONS: Record<string, string> = {
  received:
    "Received on a spool already open or used up, or the first scan of a tag that was linked " +
    "to a spool added by hand.",
  opened: "Opened a spool that was used up, from a scan queued while the scanner was offline.",
  empty: "Used up on a spool that was never opened, so both dates were set.",
};

export function flaggedText(event: EventOut): ItemText {
  return {
    title: `${eventTitle(event.type)}, flagged`,
    body: FLAG_REASONS[event.type] ?? "Recorded out of order.",
  };
}

export function tagText(tag: UnidentifiedTag): ItemText {
  if (!tag.readable) {
    return {
      title: "Unreadable tag",
      body: "Some sectors would not authenticate, so only the UID was kept. Its raw data is stored for re-decoding.",
    };
  }
  const type = tag.decoded?.detailed_filament_type ?? tag.decoded?.filament_type;
  return {
    title: typeof type === "string" && type ? `Unknown tag (${type})` : "Unknown tag",
    body: "The tag decoded, but it could not be matched to a spool. Its raw data is stored for re-decoding.",
  };
}

/** The spool an event belongs to, as "Black PLA Basic #3". */
export function spoolName(event: EventOut): string {
  return `${event.product_name} #${event.spool_id}`;
}
