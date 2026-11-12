import assert from "node:assert/strict";
import { test } from "node:test";
import { PREDICT_MAX_SECONDS, predict, turnTowards } from "../../src/geo.ts";
import { CORRECTION_MS, CarMotion } from "../../src/motion.ts";

const motion = (smooth = true) => new CarMotion(predict, turnTowards, () => smooth, PREDICT_MAX_SECONDS);
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
  car.update(fix(10.001, 0), null, 5000);
  assert.ok(Math.abs(car.at(5000).position[0] - 10) < 1e-9);
  const halfway = car.at(5000 + CORRECTION_MS / 2).position[0];
  assert.ok(halfway > 10 && halfway < 10.001);
  assert.ok(Math.abs(car.at(5000 + CORRECTION_MS).position[0] - 10.001) < 1e-9);
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
