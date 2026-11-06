/**
 * The car as the card knows it: one snapshot, then whatever changes.
 *
 * Import-free, and free of the DOM. The server sends only what changed, so a
 * value going to null arrives as null and must clear what the card holds: that is
 * how hiding the destination takes it off a screen that already has it.
 */

export type TrailPoint = [number, number, number];

export interface DriveState {
  state: string;
  driving: boolean;
  hidden: boolean;
  destination_status: string;
  destination: string | null;
  destination_latitude: number | null;
  destination_longitude: number | null;
  heading_home: boolean | null;
  arrival_at: number | null;
  minutes: number | null;
  distance: number | null;
  arrival_battery: number | null;
  traffic_delay: number | null;
  route: [number, number][] | null;
  latitude: number | null;
  longitude: number | null;
  heading: number | null;
  speed: number | null;
  battery: number | null;
  position_at: number | null;
  trip_started_at: number | null;
  trip_distance: number | null;
  trip_duration: number | null;
  model: string | null;
  paint: string | null;
  roof: string | null;
  trail: TrailPoint[];
}

export type FeedMessage =
  | ({ type: "snapshot" } & DriveState)
  | ({ type: "delta" } & Partial<DriveState>)
  | { type: "closed" };

/** About the server's own step, so the two trails stay alike. */
const TRAIL_STEP_DEGREES = 0.0002;
const MAX_TRAIL_POINTS = 3000;

/** Past this with no fix, a moving car's marker says how old it is. */
export const STALE_SECONDS = 30;

function extendTrail(trail: TrailPoint[], latitude: number, longitude: number, at: number): TrailPoint[] {
  const last = trail[trail.length - 1];
  if (last && Math.abs(last[0] - latitude) + Math.abs(last[1] - longitude) < TRAIL_STEP_DEGREES) return trail;
  const next: TrailPoint[] = [...trail, [latitude, longitude, at]];
  return next.length > MAX_TRAIL_POINTS ? next.slice(next.length - MAX_TRAIL_POINTS) : next;
}

/** The state after one message, or the same object if nothing changed. */
export function applyMessage(current: DriveState | null, message: FeedMessage, now: number): DriveState | null {
  if (message.type === "closed") return current;
  if (message.type === "snapshot") {
    const { type: _type, ...snapshot } = message;
    return snapshot;
  }
  if (current === null) return null;
  const { type: _type, ...delta } = message;
  const next: DriveState = { ...current, ...delta };
  // A new trip restarts the trail. Its end leaves the last one on the map.
  if (delta.trip_started_at != null) next.trail = [];
  if (next.trip_started_at !== null && next.latitude !== null && next.longitude !== null) {
    next.trail = extendTrail(next.trail, next.latitude, next.longitude, now);
  }
  return next;
}

/** The trail as a line, limited to recent minutes when the card asks for that. */
export function visibleTrail(trail: TrailPoint[], minutes: number | undefined, now: number): [number, number][] {
  const from = minutes === undefined ? 0 : now - minutes * 60;
  return trail.filter((point) => point[2] >= from).map((point) => [point[0], point[1]]);
}

export function isStale(state: DriveState, lastFixAt: number, now: number): boolean {
  return state.driving && now - lastFixAt > STALE_SECONDS;
}
