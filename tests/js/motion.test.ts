import assert from "node:assert/strict";
import { test } from "node:test";
import { predict, turnTowards } from "../../src/geo.ts";
import { CORRECTION_MS, CarMotion } from "../../src/motion.ts";

const motion = (smooth = true) => new CarMotion(predict, turnTowards, () => smooth);
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
