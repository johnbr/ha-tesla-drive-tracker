import assert from "node:assert/strict";
import { test } from "node:test";
import { formatAge, formatDistance, formatMinutes, formatSpeed, formatTime, unitFor } from "../../src/format.ts";

test("minutes", () => {
  assert.equal(formatMinutes(12), "12 min");
  assert.equal(formatMinutes(65), "1 h 5 min");
  assert.equal(formatMinutes(120), "2 h");
});

test("distance and speed follow the unit", () => {
  assert.equal(formatDistance(7.5, "mi"), "7.5 mi");
  assert.equal(formatDistance(20, "mi"), "20 mi");
  assert.equal(formatDistance(10, "km"), "16 km");
  assert.equal(formatSpeed(60, "mi"), "60 mph");
  assert.equal(formatSpeed(60, "km"), "97 km/h");
});

test("age", () => {
  assert.equal(formatAge(45), "45 s");
  assert.equal(formatAge(300), "5 min");
});

test("time follows the profile", () => {
  assert.match(formatTime(0, "en-US", true), /12:00/);
  assert.equal(formatTime(0, "en-GB", false), "00:00");
});

test("units follow Home Assistant unless the card says", () => {
  assert.equal(unitFor("auto", "km"), "km");
  assert.equal(unitFor("auto", "mi"), "mi");
  assert.equal(unitFor("km", "mi"), "km");
});
