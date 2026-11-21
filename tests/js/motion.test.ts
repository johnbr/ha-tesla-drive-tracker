import assert from "node:assert/strict";
import { test } from "node:test";
import * as geo from "../../src/geo.ts";
import type { LatLng } from "../../src/geo.ts";
import { CORRECTION_MS, CarMotion, MAX_CORRECTION_MS } from "../../src/motion.ts";

const motion = (smooth = true) => new CarMotion(geo, () => smooth);
const fix = (latitude: number, speed = 60) => ({
  position: [latitude, 20] as [number, number],
  heading: 0,
  speed,
});

test("the first fix is drawn where it is", () => {
  const car = motion();
  car.update(fix(10), null, 0);
  assert.deepEqual(car.at(0).position, [10, 20]);
});

test("the car moves on between fixes", () => {
  const car = motion();
  car.update(fix(10), null, 0);
  assert.ok(car.at(2000).position[0] > 10);
});

test("a correction is spread out rather than jumped", () => {
  const car = motion();
  car.update(fix(10, 0), null, 0);
  // Far enough apart in time that the fixes don't pace the car.
  car.update(fix(10.001, 0), null, 10000);
  assert.ok(Math.abs(car.at(10000).position[0] - 10) < 1e-9);
  const halfway = car.at(10000 + CORRECTION_MS / 2).position[0];
  assert.ok(halfway > 10 && halfway < 10.001);
  assert.ok(Math.abs(car.at(10000 + CORRECTION_MS).position[0] - 10.001) < 1e-9);
});

test("with smoothing off the car sits on the fix", () => {
  const car = motion(false);
  car.update(fix(10), null, 0);
  assert.deepEqual(car.at(4000).position, [10, 20]);
  assert.equal(car.moving(4000), false);
});

test("a parked car stops asking for frames", () => {
  const car = motion();
  car.update(fix(10, 0), null, 0);
  assert.equal(car.moving(CORRECTION_MS + 1), false);
  car.update(fix(10, 30), null, 5000);
  assert.equal(car.moving(9000), true);
});

test("a speed arriving just after a fix keeps the correction going", () => {
  const car = motion();
  car.update(fix(10, 0), null, 0);
  car.update(fix(10.001, 0), null, 5000);
  car.carryOn({ speed: 0.5 }, 5030);
  const done = car.at(5000 + CORRECTION_MS).position[0];
  assert.ok(Math.abs(done - 10.001) < 1e-5, `drawn at ${done}, not at the fix`);
});

test("a new heading turns the car where it is drawn and aims it", () => {
  const car = motion();
  car.update(fix(10), null, 0);
  const before = car.at(1000).position;
  car.carryOn({ heading: 90 }, 1000);
  assert.deepEqual(car.at(1000).position, before);
  const later = car.at(2000);
  assert.ok(Math.abs(later.position[0] - before[0]) < 1e-9, "kept going north");
  assert.ok(later.position[1] > before[1]);
  assert.equal(later.heading, 90);
});

test("the cap still counts from the last position", () => {
  const car = motion();
  car.update(fix(10), null, 0);
  car.carryOn({ speed: 61 }, 10000);
  assert.deepEqual(car.at(20000).position, car.at(30000).position);
});

test("a fix beside the route never flicks the car across it", () => {
  const route: LatLng[] = [
    [10, 20],
    [10.02, 20],
  ];
  const car = motion();
  car.update(fix(10), route, 0);
  car.update({ position: [10.0008, 20.0001], heading: 0, speed: 60 }, route, 3000);
  for (let now = 3000; now <= 3000 + CORRECTION_MS; now += 16) {
    const east = car.at(now).position[1];
    assert.ok(east > 20 - 1e-9 && east < 20.0001 + 1e-9, `drawn at ${east} at ${now} ms`);
  }
});

/** A fix `metres` north of latitude 10, heading north. */
const north = (metres: number, speed: number | null = 30) => ({
  position: [10 + metres / 111195, 20] as LatLng,
  heading: 0,
  speed,
});
const metresNorth = (position: LatLng) => (position[0] - 10) * 111195;

test("a car braking between fixes is drawn stopping, not running on at its last speed", () => {
  const car = motion();
  // The reported 30 mph never changes; the fixes show the car slowing.
  car.update(north(0), null, 0);
  car.update(north(20), null, 2000);
  car.update(north(30), null, 4000);
  const stopped = metresNorth(car.at(14000).position);
  assert.ok(stopped > 30 && stopped < 35, `drawn ${stopped.toFixed(1)} m north`);
});

test("a reported speed fresher than the fixes paces the car", () => {
  const car = motion();
  car.update(north(0), null, 0);
  car.carryOn({ speed: 45 }, 1500);
  car.update(north(20, 45), null, 2000);
  const second = geo.metres(car.at(11000).position, car.at(12000).position);
  assert.ok(Math.abs(second - 45 * 0.44704) < 0.1, `${second.toFixed(1)} m in a second`);
});

test("a fix behind the car is let catch up rather than backing the car up", () => {
  const car = motion();
  car.update(north(0), null, 0);
  // Drawn about 27 m on by now; the car had only got 7 m.
  car.update(north(7), null, 2000);
  let before = metresNorth(car.at(2000).position);
  for (let now = 2016; now <= 2000 + MAX_CORRECTION_MS; now += 16) {
    const here = metresNorth(car.at(now).position);
    assert.ok(here >= before, `backed up from ${before.toFixed(2)} to ${here.toFixed(2)} m at ${now} ms`);
    before = here;
  }
});

test("a car stopped past its fix eases back to it slowly", () => {
  const car = motion();
  car.update(north(0), null, 0);
  car.carryOn({ speed: 0 }, 1500);
  car.update(north(5, 0), null, 2000);
  assert.ok(metresNorth(car.at(2000 + CORRECTION_MS).position) > 6);
  assert.ok(Math.abs(metresNorth(car.at(2000 + MAX_CORRECTION_MS).position) - 5) < 0.01);
});

test("the heading leads until a position is overdue, then the route", () => {
  // North for about 56 m, then east.
  const route: LatLng[] = [
    [10, 20],
    [10.0005, 20],
    [10.0005, 20.01],
  ];
  const car = motion();
  car.update(north(0), route, 0);
  assert.equal(car.at(4500).position[1], 20, "carried straight on past the bend");
  assert.ok(car.at(8000).position[1] > 20, "turned along the route");
});

test("with smoothing off, a new heading or speed doesn't move the car", () => {
  const car = motion(false);
  car.update(fix(10), null, 0);
  car.carryOn({ heading: 90, speed: 70 }, 5000);
  assert.deepEqual(car.at(5000).position, [10, 20]);
});
