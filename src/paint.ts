/**
 * Tesla's paint names as colours.
 *
 * Import-free. The car reports a name such as `SteelGrey`; these are close
 * matches for a small marker, not colour references. A name not listed here gets
 * a neutral grey rather than a guess.
 */

const PAINTS: Record<string, string> = {
  black: "#17181a",
  solidblack: "#17181a",
  obsidianblack: "#1f2023",
  diamondblack: "#1c1d20",
  white: "#eff0ef",
  pearlwhite: "#eff0ef",
  pearlwhitemulticoat: "#eff0ef",
  solidwhite: "#f4f4f2",
  silver: "#b6babd",
  silvermetallic: "#b6babd",
  midnightsilver: "#50555a",
  midnightsilvermetallic: "#50555a",
  quicksilver: "#a7abae",
  titanium: "#8d8b84",
  steelgrey: "#6d7276",
  stealthgrey: "#4a4e52",
  grey: "#6d7276",
  deepblue: "#1f3a6e",
  deepbluemetallic: "#1f3a6e",
  oceanblue: "#1d5b8c",
  blue: "#1f3a6e",
  red: "#a31621",
  redmulticoat: "#a31621",
  multicoatred: "#a31621",
  ultrared: "#b0121f",
  midnightcherryred: "#5a0f1f",
  brown: "#4c3a2f",
  green: "#2a4b3a",
};

export const UNKNOWN_PAINT = "#7d8286";
const GLASS = "#20262c";

/** A colour for what the card config and the car say, the config winning. */
export function paintColor(configured: string, reported: string | null | undefined): string {
  const name = configured === "auto" ? reported ?? "" : configured;
  if (/^#[0-9a-fA-F]{6}$/.test(name)) return name;
  return PAINTS[name.toLowerCase().replace(/[^a-z]/g, "")] ?? UNKNOWN_PAINT;
}

/**
 * The roof's colour. The car says `None` when the roof is glass, and a roof in
 * body colour reports the paint.
 */
export function roofColor(configured: string, reported: string | null | undefined, paint: string): string {
  if (configured === "body") return paint;
  if (configured === "glass") return GLASS;
  const name = (reported ?? "").toLowerCase();
  return name === "" || name === "none" || name.includes("glass") ? GLASS : paint;
}

/**
 * The line drawn inside the white outline, chosen against the paint. A grey car
 * vanished on asphalt until the marker had two tones, and a dark car needs the
 * opposite of a light one.
 */
export function outlineColor(paint: string): string {
  const value = parseInt(paint.slice(1), 16);
  const light = (0.299 * (value >> 16) + 0.587 * ((value >> 8) & 255) + 0.114 * (value & 255)) / 255;
  return light > 0.45 ? "#1c1e21" : "#55595e";
}
