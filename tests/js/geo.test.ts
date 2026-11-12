import assert from "node:assert/strict";
import { test } from "node:test";
import { PREDICT_MAX_SECONDS, bearing, metres, nearestOnLine, predict, routeAhead, turnTowards } from "../../src/geo.ts";
import type { LatLng } from "../../src/geo.ts";

const NORTH: LatLng[] = [
  [10, 20],
  [10.01, 20],
  [10.02, 20],
];
const at = (latitude: number): LatLng => [latitude, 20];

test("distance and bearing", () => {
  assert.ok(Math.abs(metres([10, 20], [10.01, 20]) - 1112) < 2);
  assert.equal(Math.round(bearing([10, 20], [10.01, 20])), 0);
  assert.equal(Math.round(bearing([10, 20], [10, 20.01])), 90);
});

test("a stopped car stays where it is", () => {
  assert.deepEqual(predict({ position: at(10), heading: 0, speed: 1 }, null, 5), at(10));
  assert.deepEqual(predict({ position: at(10), heading: 0, speed: null }, null, 5), at(10));
});

test("with no route the car carries on along its heading", () => {
  const ahead = predict({ position: at(10), heading: 0, speed: 60 }, null, 10);
  assert.ok(Math.abs(metres(at(10), ahead) - 268) < 2);
  assert.ok(ahead[0] > 10);
});

test("no heading and no route means no guess", () => {
  assert.deepEqual(predict({ position: at(10), heading: null, speed: 60 }, null, 10), at(10));
});

test("a car on its route follows the route, not its heading", () => {
  const ahead = predict({ position: at(10.001), heading: 30, speed: 60 }, NORTH, 10);
  assert.ok(ahead[0] > 10.001);
  assert.ok(Math.abs(ahead[1] - 20) < 1e-9);
});

test("a car facing across its route is not slid along it", () => {
  const ahead = predict({ position: at(10.001), heading: 90, speed: 60 }, NORTH, 10);
  assert.ok(ahead[1] > 20);
  assert.ok(Math.abs(ahead[0] - 10.001) < 1e-9);
});

test("a car that has left its route falls back on its heading", () => {
  const ahead = predict({ position: [10.001, 20.01], heading: 90, speed: 60 }, NORTH, 10);
  assert.ok(ahead[1] > 20.01);
});

test("prediction stops at the cap", () => {
  const fix = { position: at(10), heading: 0, speed: 60 };
  assert.deepEqual(predict(fix, null, PREDICT_MAX_SECONDS), predict(fix, null, 500));
});

test("prediction stops at the end of the route", () => {
  const end = predict({ position: at(10.0199), heading: 0, speed: 80 }, NORTH, 15);
  assert.deepEqual(end, at(10.02));
});

test("the route ahead starts at the car", () => {
  const ahead = routeAhead(NORTH, at(10.015));
  assert.equal(ahead.length, 2);
  assert.ok(Math.abs(ahead[0][0] - 10.015) < 1e-9);
  assert.deepEqual(ahead[1], at(10.02));
});

test("a car off its route keeps the whole route", () => {
  assert.equal(routeAhead(NORTH, [10.01, 21]).length, 3);
  assert.equal(routeAhead(NORTH, null).length, 3);
});

test("nearest point lies on the line", () => {
  const near = nearestOnLine(NORTH, [10.005, 20.0001]);
  assert.equal(near?.index, 0);
  assert.ok(near && near.off < 12);
});

test("turning takes the short way round", () => {
  assert.equal(Math.round(turnTowards(350, 10, 0.5)), 0);
  assert.equal(Math.round(turnTowards(10, 350, 0.5)), 0);
  assert.equal(turnTowards(90, 180, 1), 180);
});

test("a car heading north is not put on a road crossing its path", () => {
  // Due east, then a long way north from the crossing.
  const route: LatLng[] = [
    [0, -0.001],
    [0, 0],
    [0.01, 0],
  ];
  const near = nearestOnLine(route, [-0.00005, -0.0002], 0);
  assert.equal(near?.index, 1);
  assert.equal(nearestOnLine(route, [-0.00005, -0.0002])?.index, 0);
});
