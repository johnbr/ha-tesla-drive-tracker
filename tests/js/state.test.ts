import assert from "node:assert/strict";
import { test } from "node:test";
import { STALE_SECONDS, applyMessage, isStale, visibleTrail } from "../../src/state.ts";
import type { DriveState } from "../../src/state.ts";

const snapshot = (over: Partial<DriveState> = {}): DriveState =>
  ({
    state: "driving",
    driving: true,
    hidden: false,
    destination: "Cafe",
    destination_latitude: 10,
    destination_longitude: 20,
    route: [
      [1, 2],
      [3, 4],
    ],
    latitude: 11,
    longitude: 21,
    trip_started_at: 100,
    trail: [[11, 21, 100]],
    ...over,
  }) as DriveState;

const start = () => applyMessage(null, { type: "snapshot", ...snapshot() }, 200);

test("a delta before any snapshot is ignored", () => {
  assert.equal(applyMessage(null, { type: "delta", speed: 40 }, 200), null);
});

test("a snapshot replaces everything", () => {
  assert.equal(start()?.destination, "Cafe");
});

test("hiding clears what the card holds", () => {
  const next = applyMessage(
    start(),
    { type: "delta", hidden: true, destination: null, destination_latitude: null, route: null },
    210
  );
  assert.equal(next?.destination, null);
  assert.equal(next?.destination_latitude, null);
  assert.equal(next?.route, null);
});

test("moving extends the trail", () => {
  const next = applyMessage(start(), { type: "delta", latitude: 11.01 }, 210);
  assert.equal(next?.trail.length, 2);
  assert.deepEqual(next?.trail[1], [11.01, 21, 210]);
});

test("a tiny move adds no point", () => {
  const next = applyMessage(start(), { type: "delta", latitude: 11.00001 }, 210);
  assert.equal(next?.trail.length, 1);
});

test("a new trip starts a new trail", () => {
  const next = applyMessage(start(), { type: "delta", trip_started_at: 900, latitude: 12 }, 910);
  assert.deepEqual(next?.trail, [[12, 21, 910]]);
});

test("the last trail stays after a trip ends", () => {
  const next = applyMessage(start(), { type: "delta", trip_started_at: null, latitude: 12 }, 910);
  assert.equal(next?.trail.length, 1);
});

test("the trail can be limited to recent minutes", () => {
  const trail: [number, number, number][] = [
    [1, 2, 100],
    [3, 4, 500],
  ];
  assert.deepEqual(visibleTrail(trail, 5, 600), [[3, 4]]);
  assert.equal(visibleTrail(trail, undefined, 600).length, 2);
});

test("only a driving car goes stale", () => {
  const drive = snapshot();
  assert.ok(!isStale(drive, 1000, 1000 + STALE_SECONDS));
  assert.ok(isStale(drive, 1000, 1001 + STALE_SECONDS));
  assert.ok(!isStale(snapshot({ driving: false }), 1000, 9000));
});
