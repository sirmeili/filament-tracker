/** What the phone decodes itself, for the screen when the server cannot be reached.
 *
 * A port of the product, type and color fields of the server's decoder
 * (server/src/filament_tracker/decoder/decode.py). The server stays the authority: this is
 * only for offline use, and the queued scan carries the raw blocks for it to decode.
 */

const DATA_BLOCKS = 48;

export interface OfflineTag {
  materialId: string;
  variantId: string;
  filamentType: string;
  detailedType: string;
  colorRgba: string;
  trayUid: string;
}

function dataIndex(absolute: number): number {
  return absolute - Math.floor(absolute / 4);
}

function bytesOf(hex: string): number[] | null {
  if (!/^[0-9A-Fa-f]{32}$/.test(hex)) return null;
  const out: number[] = [];
  for (let i = 0; i < 32; i += 2) out.push(parseInt(hex.slice(i, i + 2), 16));
  return out;
}

/** A NUL-padded ASCII string; anything outside printable ASCII reads as U+FFFD, as on the server. */
function text(raw: number[]): string {
  const end = raw.indexOf(0);
  return (end < 0 ? raw : raw.slice(0, end))
    .map((b) => (b < 0x80 ? String.fromCharCode(b) : "�"))
    .join("")
    .trim();
}

function hex(raw: number[]): string {
  return raw
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("")
    .toUpperCase();
}

/** Decode the fields the screen needs; null if the blocks are not a readable Bambu tag. */
export function decodeOffline(blocks: string[]): OfflineTag | null {
  if (blocks.length !== DATA_BLOCKS) return null;
  const parsed = blocks.map(bytesOf);
  if (parsed.some((b) => b === null)) return null;
  const block = (absolute: number): number[] => parsed[dataIndex(absolute)] as number[];

  const materialVariant = block(1);
  const materialId = text(materialVariant.slice(8, 16));
  const tray = block(9);
  if (!materialId || tray.every((b) => b === 0)) return null;
  return {
    materialId,
    variantId: text(materialVariant.slice(0, 8)),
    filamentType: text(block(2)),
    detailedType: text(block(4)),
    colorRgba: hex(block(5).slice(0, 4)),
    trayUid: hex(tray),
  };
}

/** A name for the screen, as the server names a new product: "PLA Basic #000000". */
export function offlineName(tag: OfflineTag): string {
  return `${tag.detailedType || tag.filamentType} #${tag.colorRgba.slice(0, 6)}`;
}
