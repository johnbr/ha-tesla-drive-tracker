/**
 * Replay recorded drives through the card's motion, and say how the car moved.
 *
 *   npm run replay -- <recording.jsonl.gz>... [--src <folder>]
 *
 * Recordings come from the integration's "Record drives for debugging" option, in
 * `tesla_drive_tracker/recordings/<entry id>/` under Home Assistant's
 * configuration folder. `--src` replays with `geo.ts`, `motion.ts` and `state.ts`
 * from another folder, such as a worktree of `main`, to compare a change with it.
 *
 * Frames run at 60 a second while the car is moving, as in the card, and are
 * measured only while driving:
 *
 * - correction: how far the drawn car was from each new fix when it arrived, which
 *   is how far off the prediction was
 * - sideways: how far the car was drawn moving across its own nose, per km
 * - jump: the furthest the car was drawn moving in a single frame
 * - off nose: frames with the car travelling more than 60 degrees off its nose
 */

import { readFileSync } from "node:fs";
import { resolve } from "node:path";
import { pathToFileURL } from "node:url";
import { gunzipSync } from "node:zlib";
import type { CarMotion as Motion } from "../src/motion.ts";
import type { DriveState, FeedMessage } from "../src/state.ts";

const FRAME_MS = 1000 / 60;
const OFF_NOSE_DEGREES = 60;

const args = process.argv.slice(2);
const at = args.indexOf("--src");
const src = resolve(at >= 0 ? args.splice(at, 2)[1] : new URL("../src", import.meta.url).pathname);
if (args.length === 0) {
  console.error("Usage: npm run replay -- <recording.jsonl.gz>... [--src <folder>]");
  process.exit(1);
}
const load = (name: string) => import(pathToFileURL(`${src}/${name}.ts`).href);
const geo = await load("geo");
const { CarMotion } = await load("motion");
const { applyMessage } = await load("state");

type Line = { t: number; type: "snapshot" | "delta" } & Partial<DriveState>;
const lines: Line[] = args
  .flatMap((file) => {
    const raw = readFileSync(file);
    const text = (file.endsWith(".gz") ? gunzipSync(raw) : raw).toString("utf8");
    return text.split("\n").filter(Boolean).map((line) => JSON.parse(line) as Line);
  })
  .sort((a, b) => a.t - b.t);

interface Trip {
  started: number;
  seconds: number;
  fixes: number;
  gaps: number[];
  corrections: number[];
  along: number;
  sideways: number;
  jump: number;
  frames: number;
  offNose: number;
}

const radians = (degrees: number): number => (degrees * Math.PI) / 180;
const angleBetween = (a: number, b: number): number => Math.abs(((a - b + 540) % 360) - 180);

/** Metres east and north from one point to another close by. */
function step(a: [number, number], b: [number, number]): [number, number] {
  return [geo.metres(a, [a[0], b[1]]) * Math.sign(b[1] - a[1]), geo.metres(a, [b[0], a[1]]) * Math.sign(b[0] - a[0])];
}

// Before the motion took the geometry whole, it took its parts.
const motion: Motion =
  CarMotion.length > 2
    ? new CarMotion(geo.predict, geo.turnTowards, () => true, geo.PREDICT_MAX_SECONDS)
    : new CarMotion(geo, () => true);
const trips = new Map<number, Trip>();
let drive: DriveState | null = null;
let lastFix: number | null = null;

function trip(): Trip | undefined {
  if (!drive?.driving || drive.trip_started_at === null) return undefined;
  const started = drive.trip_started_at;
  if (!trips.has(started)) {
    trips.set(started, {
      started,
      seconds: 0,
      fixes: 0,
      gaps: [],
      corrections: [],
      along: 0,
      sideways: 0,
      jump: 0,
      frames: 0,
      offNose: 0,
    });
  }
  return trips.get(started);
}

/** Frames from `from` up to `to`, while the car is moving. */
function frames(from: number, to: number): void {
  let before = motion.at(from);
  for (let now = from + FRAME_MS; now < to && motion.moving(now); now += FRAME_MS) {
    const drawn = motion.at(now);
    const current = trip();
    if (current) {
      current.seconds += FRAME_MS / 1000;
      const [east, north] = step(before.position, drawn.position);
      const moved = Math.hypot(east, north);
      current.jump = Math.max(current.jump, moved);
      if (drawn.heading !== null) {
        const nose = radians(drawn.heading);
        current.along += Math.abs(east * Math.sin(nose) + north * Math.cos(nose));
        current.sideways += Math.abs(east * Math.cos(nose) - north * Math.sin(nose));
        if (moved > 0.05) {
          current.frames += 1;
          const travel = (Math.atan2(east, north) * 180) / Math.PI;
          if (angleBetween(travel, drawn.heading) > OFF_NOSE_DEGREES) current.offNose += 1;
        }
      }
    }
    before = drawn;
  }
}

// What the card does with each message, as in its `_onMessage`.
for (let index = 0; index < lines.length; index += 1) {
  const { t, type, ...fields } = lines[index];
  const now = t * 1000;
  const message = (type === "snapshot" ? { type, trail: [], ...fields } : { type, ...fields }) as FeedMessage;
  const previous = drive;
  const next: DriveState | null = applyMessage(previous, message, t);
  if (next === null) continue;
  const moved =
    type === "snapshot" || previous?.latitude !== next.latitude || previous?.longitude !== next.longitude;
  drive = next;
  if (moved && next.latitude !== null && next.longitude !== null) {
    const fix: [number, number] = [next.latitude, next.longitude];
    const current = trip();
    if (current && previous && type === "delta") {
      current.fixes += 1;
      if (lastFix !== null) current.gaps.push(t - lastFix);
      current.corrections.push(geo.metres(motion.at(now).position, fix));
    }
    lastFix = t;
    motion.update({ position: fix, heading: next.heading, speed: next.speed }, next.route, now);
  } else if (!moved) {
    motion.carryOn({ speed: next.speed, heading: next.heading }, now);
  }
  const until = index + 1 < lines.length ? lines[index + 1].t * 1000 : now;
  frames(now, until);
}

const percentile = (values: number[], part: number): number => {
  if (values.length === 0) return NaN;
  const sorted = [...values].sort((a, b) => a - b);
  return sorted[Math.min(sorted.length - 1, Math.floor(sorted.length * part))];
};

const rows = [...trips.values()].filter((row) => row.fixes > 0);
const total: Trip = {
  started: NaN,
  seconds: rows.reduce((sum, row) => sum + row.seconds, 0),
  fixes: rows.reduce((sum, row) => sum + row.fixes, 0),
  gaps: rows.flatMap((row) => row.gaps),
  corrections: rows.flatMap((row) => row.corrections),
  along: rows.reduce((sum, row) => sum + row.along, 0),
  sideways: rows.reduce((sum, row) => sum + row.sideways, 0),
  jump: Math.max(0, ...rows.map((row) => row.jump)),
  frames: rows.reduce((sum, row) => sum + row.frames, 0),
  offNose: rows.reduce((sum, row) => sum + row.offNose, 0),
};

const table = [...rows, ...(rows.length > 1 ? [total] : [])].map((row) => ({
  trip: Number.isNaN(row.started) ? "all" : new Date(row.started * 1000).toLocaleString(),
  minutes: (row.seconds / 60).toFixed(1),
  fixes: row.fixes,
  "every (s)": percentile(row.gaps, 0.5).toFixed(1),
  "correction median (m)": percentile(row.corrections, 0.5).toFixed(1),
  "correction p90 (m)": percentile(row.corrections, 0.9).toFixed(1),
  "sideways (m/km)": ((row.sideways / Math.max(row.along, 1)) * 1000).toFixed(1),
  "jump (m)": row.jump.toFixed(2),
  "off nose": `${((row.offNose / Math.max(row.frames, 1)) * 100).toFixed(1)}%`,
}));
if (table.length === 0) console.log("No driving in these recordings.");
else console.table(table);
