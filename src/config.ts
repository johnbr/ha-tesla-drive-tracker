/**
 * Card config parsing and validation.
 *
 * Import-free on purpose: `node --test` strips the types and runs this file
 * directly. Validation is strict: an unknown key or a wrong shape throws, so a
 * typo can't silently become the default.
 */

/** Keys Lovelace and the layout helpers write onto a card config. */
const FRAME_KEYS = new Set(["type", "view_layout", "layout_options", "grid_options", "visibility", "card_mod"]);

export const CARD_TYPE = "tesla-drive-tracker-card";
export const EDITOR_TYPE = "tesla-drive-tracker-card-editor";

export const MODELS = ["auto", "s", "3", "x", "y", "cybertruck"] as const;
export const ROOFS = ["auto", "glass", "body"] as const;
export const MARKER_STYLES = ["car", "arrow", "dot"] as const;
export const FOLLOWS = ["auto", "car", "fit", "off"] as const;
export const HUDS = ["full", "compact", "off"] as const;
export const HUD_POSITIONS = ["top", "bottom"] as const;
export const UNITS = ["auto", "mi", "km"] as const;
export const WHEN_PARKED = ["map", "compact", "hide"] as const;
export const HUD_FIELDS = [
  "destination",
  "eta",
  "minutes",
  "distance",
  "speed",
  "battery",
  "arrival_battery",
  "traffic_delay",
] as const;

export type HudField = (typeof HUD_FIELDS)[number];

export interface CardConfig {
  entry_id?: string;
  model: (typeof MODELS)[number];
  color: string;
  roof: (typeof ROOFS)[number];
  image?: string;
  image_nose: number;
  marker_style: (typeof MARKER_STYLES)[number];
  marker_size: number;
  follow: (typeof FOLLOWS)[number];
  recenter_after: number;
  speed_zoom: boolean;
  height: number;
  show_zones: boolean;
  show_route: boolean;
  route_color: string;
  show_trail: boolean;
  trail_color: string;
  trail_minutes?: number;
  hud: (typeof HUDS)[number];
  hud_fields: HudField[];
  hud_position: (typeof HUD_POSITIONS)[number];
  units: (typeof UNITS)[number];
  when_parked: (typeof WHEN_PARKED)[number];
  smooth_motion: boolean;
}

export const DEFAULTS: CardConfig = {
  model: "auto",
  color: "auto",
  roof: "auto",
  image_nose: 0,
  marker_style: "car",
  marker_size: 64,
  follow: "auto",
  recenter_after: 20,
  speed_zoom: true,
  height: 400,
  show_zones: false,
  show_route: true,
  route_color: "#1a73e8",
  show_trail: true,
  trail_color: "#9c6ade",
  hud: "full",
  hud_fields: ["destination", "eta", "minutes", "distance", "speed", "battery", "arrival_battery", "traffic_delay"],
  hud_position: "bottom",
  units: "auto",
  when_parked: "map",
  smooth_motion: true,
};

const HEX = /^#[0-9a-fA-F]{6}$/;

/**
 * Whether a picture may be used.
 *
 * Only this Home Assistant's own paths or https. A `data:` or `javascript:` URL,
 * or a protocol-relative `//host`, is refused.
 */
export function safeImage(url: string): boolean {
  if (url.startsWith("/")) return !url.startsWith("//") && !url.includes("\\");
  return /^https:\/\/[^\s]+$/.test(url);
}

function oneOf<T extends string>(key: string, value: unknown, options: readonly T[]): T {
  if (typeof value === "string" && (options as readonly string[]).includes(value)) return value as T;
  throw new Error(`${key} must be one of: ${options.join(", ")}`);
}

function aNumber(key: string, value: unknown, min: number, max: number): number {
  if (typeof value === "number" && Number.isFinite(value) && value >= min && value <= max) return value;
  throw new Error(`${key} must be a number from ${min} to ${max}`);
}

function aBoolean(key: string, value: unknown): boolean {
  if (typeof value === "boolean") return value;
  throw new Error(`${key} must be true or false`);
}

function aHex(key: string, value: unknown): string {
  if (typeof value === "string" && HEX.test(value)) return value;
  throw new Error(`${key} must be a colour like #1a73e8`);
}

const CHECKS: Record<string, (key: string, value: unknown) => unknown> = {
  entry_id: (key, value) => {
    if (typeof value === "string" && value) return value;
    throw new Error(`${key} must be a car's id`);
  },
  model: (key, value) => oneOf(key, value, MODELS),
  color: (key, value) => {
    // A hex, "auto", or one of Tesla's paint names, which are plain words.
    if (typeof value === "string" && /^(#[0-9a-fA-F]{6}|[A-Za-z]+)$/.test(value)) return value;
    throw new Error(`${key} must be auto, a paint name or a colour like #6d7276`);
  },
  roof: (key, value) => oneOf(key, value, ROOFS),
  image: (key, value) => {
    if (typeof value === "string" && safeImage(value)) return value;
    throw new Error(`${key} must be a path on this Home Assistant or an https URL`);
  },
  image_nose: (key, value) => aNumber(key, value, 0, 359),
  marker_style: (key, value) => oneOf(key, value, MARKER_STYLES),
  marker_size: (key, value) => aNumber(key, value, 24, 160),
  follow: (key, value) => oneOf(key, value, FOLLOWS),
  recenter_after: (key, value) => aNumber(key, value, 0, 600),
  speed_zoom: aBoolean,
  height: (key, value) => aNumber(key, value, 120, 1200),
  show_zones: aBoolean,
  show_route: aBoolean,
  route_color: aHex,
  show_trail: aBoolean,
  trail_color: aHex,
  trail_minutes: (key, value) => aNumber(key, value, 1, 1440),
  hud: (key, value) => oneOf(key, value, HUDS),
  hud_fields: (key, value) => {
    if (Array.isArray(value) && value.length) return value.map((item) => oneOf(key, item, HUD_FIELDS));
    throw new Error(`${key} must list at least one of: ${HUD_FIELDS.join(", ")}`);
  },
  hud_position: (key, value) => oneOf(key, value, HUD_POSITIONS),
  units: (key, value) => oneOf(key, value, UNITS),
  when_parked: (key, value) => oneOf(key, value, WHEN_PARKED),
  smooth_motion: aBoolean,
};

/** Validate a dashboard's config, filling in what it leaves out. */
export function parseConfig(raw: unknown): CardConfig {
  if (typeof raw !== "object" || raw === null) throw new Error("Invalid configuration");
  const parsed: Record<string, unknown> = { ...DEFAULTS };
  for (const [key, value] of Object.entries(raw)) {
    if (FRAME_KEYS.has(key)) continue;
    const check = CHECKS[key];
    if (!check) throw new Error(`Unknown option: ${key}`);
    parsed[key] = check(key, value);
  }
  return parsed as unknown as CardConfig;
}
