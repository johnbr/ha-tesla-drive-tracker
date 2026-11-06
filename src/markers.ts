/**
 * The car on the map: original top-down drawings, nose up.
 *
 * Import-free. Each is plain SVG with paint and roof as CSS variables, so one
 * drawing serves every colour. The heading is applied by rotating the element,
 * which is what makes the old 36 pictures per car unnecessary.
 *
 * Every colour here has already been through `paint.ts`, which returns only hex
 * values, so nothing from a config or the car reaches this markup unchecked.
 */

export type Model = "s" | "3" | "x" | "y" | "cybertruck";

export interface Look {
  paint: string;
  roof: string;
  outline: string;
}

const VIEW = "0 0 64 128";

interface Shape {
  body: string;
  windscreen: string;
  roof: string;
  rear: string;
  sides: string[];
  /** Mirror centres on the left; the right is mirrored. */
  mirror: [number, number];
  lights: { head: string[]; tail: string[] };
  /** Lines on the paint, such as door seams. */
  seams: string[];
}

/** A left-hand path and its mirror image about the car's centre line. */
function both(left: string): string[] {
  const right = left.replace(/(-?\d+(?:\.\d+)?),(-?\d+(?:\.\d+)?)/g, (_, x: string, y: string) => `${64 - Number(x)},${y}`);
  return [left, right];
}

const SHAPES: Record<Model, Shape> = {
  // Long and low, with the longest bonnet and a tapered liftback.
  s: {
    body: "M32,3 C42,3 49,6 51.5,14 L54,29 C56,36 56,44 55.5,52 L55.5,92 C56,102 55,110 52,116 C49,122 42,125 32,125 C22,125 15,122 12,116 C9,110 8,102 8.5,92 L8.5,52 C8,44 8,36 10,29 L12.5,14 C15,6 22,3 32,3 Z",
    windscreen: "M16,44 C23,38 41,38 48,44 L45,59 C38,56 26,56 19,59 Z",
    roof: "M19,61 C26,58 38,58 45,61 L45,90 C38,92 26,92 19,90 Z",
    rear: "M19,92 C26,94 38,94 45,92 L47,106 C40,110 24,110 17,106 Z",
    sides: both("M14.5,47 L17,60 L17,89 L15.5,102 C12.5,92 12.5,58 14.5,47 Z"),
    mirror: [7.5, 46],
    lights: {
      head: both("M14,12 C17,8 21,6.5 25,6"),
      tail: both("M13,116 C17,120 21,122 26,122.5"),
    },
    seams: both("M21,16 C20,24 19,31 18,39"),
  },
  // Shorter and rounder, one sweep of glass from the screen to the tail.
  "3": {
    body: "M32,8 C41,8 48,11 50.5,18 L53,31 C55,38 55,46 54.5,54 L54.5,90 C55,99 54,106 51,112 C48,117 41,120 32,120 C23,120 16,117 13,112 C10,106 9,99 9.5,90 L9.5,54 C9,46 9,38 11,31 L13.5,18 C16,11 23,8 32,8 Z",
    windscreen: "M16,42 C23,34 41,34 48,42 L45.5,60 C38,57 26,57 18.5,60 Z",
    roof: "M18.5,61.5 C26,59 38,59 45.5,61.5 L45.5,84 C38,86 26,86 18.5,84 Z",
    rear: "M18.5,85.5 C26,87.5 38,87.5 45.5,85.5 L47,101 C40,105 24,105 17,101 Z",
    sides: both("M14.5,45 L17,60 L17,84 L15.5,98 C12.5,88 12.5,56 14.5,45 Z"),
    mirror: [8.5, 44],
    lights: {
      head: both("M15,17 C18,13 22,11.5 26,11"),
      tail: both("M14,111 C18,115 22,117 27,117.5"),
    },
    seams: both("M21,20 C20,26 19,31 18,36"),
  },
  // Broad and tall, with a huge screen and the seams of doors that open upwards.
  x: {
    body: "M32,4 C43,4 51,7 53.5,15 L56,29 C58,38 58,46 57.5,54 L57.5,94 C58,104 57,111 54,117 C51,122 43,125 32,125 C21,125 13,122 10,117 C7,111 6,104 6.5,94 L6.5,54 C6,46 6,38 8,29 L10.5,15 C13,7 21,4 32,4 Z",
    windscreen: "M15,36 C23,28 41,28 49,36 L46,60 C38,57 26,57 18,60 Z",
    roof: "M18,62 C26,59 38,59 46,62 L46,98 C38,100 26,100 18,98 Z",
    rear: "M18,100 C26,102 38,102 46,100 L47.5,110 C40,114 24,114 16.5,110 Z",
    sides: both("M13.5,40 L16.5,61 L16.5,97 L15,108 C11.5,96 11.5,54 13.5,40 Z"),
    mirror: [5.5, 42],
    lights: {
      head: both("M12.5,13 C16,9 20,7.5 25,7"),
      tail: both("M11.5,117 C16,121 21,122.5 26,123"),
    },
    seams: ["M32,62 L32,98", "M18,80 C26,78 38,78 46,80"],
  },
  // A Model 3's front on a taller, fuller back.
  y: {
    body: "M32,6 C42,6 49,9 51.5,17 L54.5,31 C56.5,39 56.5,47 56,55 L56,93 C56.5,102 55.5,109 52.5,115 C49.5,120 42,123 32,123 C22,123 14.5,120 11.5,115 C8.5,109 7.5,102 8,93 L8,55 C7.5,47 7.5,39 9.5,31 L12.5,17 C15,9 22,6 32,6 Z",
    windscreen: "M15.5,40 C23,32 41,32 48.5,40 L46,60 C38,57 26,57 18,60 Z",
    roof: "M18,61.5 C26,59 38,59 46,61.5 L46,92 C38,94 26,94 18,92 Z",
    rear: "M18,93.5 C26,95.5 38,95.5 46,93.5 L47.5,107 C40,111 24,111 16.5,107 Z",
    sides: both("M14,44 L16.8,60 L16.8,91 L15,104 C12,92 12,56 14,44 Z"),
    mirror: [7, 43],
    lights: {
      head: both("M14,15 C17.5,11 21.5,9.5 26,9"),
      tail: both("M13,114 C17,118 22,120 27,120.5"),
    },
    seams: both("M21,19 C20,25 19,30 18,35"),
  },
  // Flat panels and hard corners, with a covered bed behind the cabin.
  cybertruck: {
    body: "M20,3 L44,3 L55,14 L57,34 L57,108 L52,124 L12,124 L7,108 L7,34 L9,14 Z",
    windscreen: "M15,30 L49,30 L45,58 L19,58 Z",
    roof: "M19,60 L45,60 L44,74 L20,74 Z",
    rear: "M20,76 L44,76 L45,84 L19,84 Z",
    sides: both("M12.5,33 L17,59 L17,84 L13,84 Z"),
    mirror: [5.5, 36],
    lights: {
      head: ["M12,12 L52,12"],
      tail: ["M13,120.5 L51,120.5"],
    },
    seams: ["M13,88 L51,88 L51,116 L13,116 Z", "M32,3 L32,28"],
  },
};

/** Fallback for a car whose model isn't known. */
const DEFAULT_MODEL: Model = "s";

function paths(list: string[], attributes: string): string {
  return list.map((d) => `<path d="${d}" ${attributes}/>`).join("");
}

export function carSvg(model: string | null | undefined, look: Look): string {
  const shape = SHAPES[(model ?? DEFAULT_MODEL) as Model] ?? SHAPES[DEFAULT_MODEL];
  const [mirrorX, mirrorY] = shape.mirror;
  const mirrors = [mirrorX, 64 - mirrorX]
    .map((x) => `<ellipse cx="${x}" cy="${mirrorY}" rx="4" ry="2.4"/>`)
    .join("");
  // White first, then a line chosen against the paint, so the car stands off both
  // pale roads and dark tarmac.
  return (
    `<svg viewBox="${VIEW}" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">` +
    `<g fill="#fff" stroke="#fff" stroke-width="5" stroke-linejoin="round">${mirrors}<path d="${shape.body}"/></g>` +
    `<g fill="${look.paint}" stroke="${look.outline}" stroke-width="2" stroke-linejoin="round">${mirrors}<path d="${shape.body}"/></g>` +
    paths(shape.seams, `fill="none" stroke="${look.outline}" stroke-width="0.8" opacity="0.55"`) +
    `<path d="${shape.windscreen}" fill="#1b2127"/>` +
    `<path d="${shape.roof}" fill="${look.roof}"/>` +
    `<path d="${shape.rear}" fill="#1b2127"/>` +
    paths(shape.sides, `fill="#1b2127"`) +
    paths(shape.lights.head, `fill="none" stroke="#f4f7fb" stroke-width="2.4" stroke-linecap="round"`) +
    paths(shape.lights.tail, `fill="none" stroke="#d3202c" stroke-width="2.4" stroke-linecap="round"`) +
    `</svg>`
  );
}

/** A navigation arrow, for those who prefer a plain mark. */
export function arrowSvg(look: Look): string {
  return (
    `<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">` +
    `<path d="M32,5 L55,57 L32,45 L9,57 Z" fill="${look.paint}" stroke="#fff" stroke-width="5" stroke-linejoin="round"/>` +
    `</svg>`
  );
}

export function dotSvg(look: Look): string {
  return (
    `<svg viewBox="0 0 64 64" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">` +
    `<circle cx="32" cy="32" r="22" fill="${look.paint}" stroke="#fff" stroke-width="6"/>` +
    `</svg>`
  );
}

export function destinationSvg(): string {
  return (
    `<svg viewBox="0 0 24 32" xmlns="http://www.w3.org/2000/svg" aria-hidden="true">` +
    `<path d="M12,1 C5.9,1 1,5.9 1,12 C1,20 12,31 12,31 C12,31 23,20 23,12 C23,5.9 18.1,1 12,1 Z" fill="#e53935" stroke="#fff" stroke-width="2"/>` +
    `<circle cx="12" cy="12" r="4" fill="#fff"/>` +
    `</svg>`
  );
}
