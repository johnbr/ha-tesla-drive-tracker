/**
 * Distances, and where the car probably is between fixes.
 *
 * Import-free. Prediction was measured against one evening of real fixes, with
 * these median errors in metres:
 *
 *   ahead   frozen marker   along heading   along route
 *    5 s          71              32             33
 *   10 s         161              56             50
 *   15 s         239              83             61
 *   20 s         311             126             86
 *   30 s         454             210            120
 *
 * So predicting beats a frozen marker about threefold, the route overtakes the
 * heading from about 10 s, and past 15 s one prediction in ten is over 200 m out,
 * which is the cap. A moving car reports within 7 s 99.9% of the time, so the cap
 * is rarely reached.
 */

export type LatLng = [number, number];

export const PREDICT_MAX_SECONDS = 15;
/** Below this a car is stopped or creeping, and predicting only adds jitter. */
export const PREDICT_MIN_MPH = 2;
/** Further than this from its line, the car has left the route. */
const ON_ROUTE_METRES = 60;

const EARTH_METRES = 6371000;
const METRES_PER_SECOND_PER_MPH = 0.44704;

const radians = (degrees: number): number => (degrees * Math.PI) / 180;
const degrees = (value: number): number => (value * 180) / Math.PI;

/** Metres between two points close enough for a flat approximation. */
export function metres(a: LatLng, b: LatLng): number {
  const x = radians(b[1] - a[1]) * Math.cos(radians((a[0] + b[0]) / 2));
  const y = radians(b[0] - a[0]);
  return EARTH_METRES * Math.hypot(x, y);
}

/** The point on a line closest to `point`, with the segment it lies on. */
export function nearestOnLine(line: LatLng[], point: LatLng): { index: number; at: LatLng; off: number } | null {
  let best: { index: number; at: LatLng; off: number } | null = null;
  for (let index = 0; index < line.length - 1; index += 1) {
    const [a, b] = [line[index], line[index + 1]];
    const scale = Math.cos(radians(a[0]));
    const dx = (b[1] - a[1]) * scale;
    const dy = b[0] - a[0];
    const px = (point[1] - a[1]) * scale;
    const py = point[0] - a[0];
    const length = dx * dx + dy * dy;
    const along = length === 0 ? 0 : Math.max(0, Math.min(1, (px * dx + py * dy) / length));
    const at: LatLng = [a[0] + (b[0] - a[0]) * along, a[1] + (b[1] - a[1]) * along];
    const off = metres(point, at);
    if (best === null || off < best.off) best = { index, at, off };
  }
  return best;
}

/** Walk a distance along a line from where the car is on it. */
export function walkLine(line: LatLng[], from: { index: number; at: LatLng }, distance: number): LatLng {
  let here = from.at;
  let left = distance;
  for (let index = from.index; index < line.length - 1; index += 1) {
    const next = line[index + 1];
    const step = metres(here, next);
    if (step >= left) {
      const part = step === 0 ? 0 : left / step;
      return [here[0] + (next[0] - here[0]) * part, here[1] + (next[1] - here[1]) * part];
    }
    left -= step;
    here = next;
  }
  return here;
}

/** Bearing in degrees from one point to the next. */
export function bearing(a: LatLng, b: LatLng): number {
  const scale = Math.cos(radians(a[0]));
  return (degrees(Math.atan2((b[1] - a[1]) * scale, b[0] - a[0])) + 360) % 360;
}

export interface Fix {
  position: LatLng;
  heading: number | null;
  speed: number | null;
}

/** Where a car is `seconds` after a fix, following its route when it is on one. */
export function predict(fix: Fix, route: LatLng[] | null, seconds: number): LatLng {
  const speed = fix.speed ?? 0;
  if (speed < PREDICT_MIN_MPH || seconds <= 0) return fix.position;
  const distance = speed * METRES_PER_SECOND_PER_MPH * Math.min(seconds, PREDICT_MAX_SECONDS);
  if (route && route.length > 1) {
    const near = nearestOnLine(route, fix.position);
    if (near && near.off <= ON_ROUTE_METRES) return walkLine(route, near, distance);
  }
  if (fix.heading === null) return fix.position;
  const heading = radians(fix.heading);
  const [latitude, longitude] = fix.position;
  return [
    latitude + degrees((distance * Math.cos(heading)) / EARTH_METRES),
    longitude + degrees((distance * Math.sin(heading)) / EARTH_METRES / Math.cos(radians(latitude))),
  ];
}

/** What is left of a route ahead of the car, or all of it if the car is off it. */
export function routeAhead(route: LatLng[], position: LatLng | null): LatLng[] {
  if (position === null || route.length < 2) return route;
  const near = nearestOnLine(route, position);
  if (near === null || near.off > ON_ROUTE_METRES) return route;
  return [near.at, ...route.slice(near.index + 1)];
}

/** The shorter way round from one heading to another. */
export function turnTowards(from: number, to: number, part: number): number {
  const delta = ((to - from + 540) % 360) - 180;
  return (from + delta * part + 360) % 360;
}
