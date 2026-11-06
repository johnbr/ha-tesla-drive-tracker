import assert from "node:assert/strict";
import { test } from "node:test";
import { viewAction, zoomForSpeed } from "../../src/follow.ts";

test("auto follows while driving and fits otherwise", () => {
  assert.equal(viewAction("auto", true, null, 20, 100), "car");
  assert.equal(viewAction("auto", false, null, 20, 100), "fit");
});

test("off never moves the view", () => {
  assert.equal(viewAction("off", true, null, 20, 100), "none");
});

test("touching the map hands it over until the delay passes", () => {
  assert.equal(viewAction("auto", true, 90, 20, 100), "none");
  assert.equal(viewAction("auto", true, 90, 20, 111), "car");
});

test("a delay of zero never recentres by itself", () => {
  assert.equal(viewAction("car", true, 10, 0, 100000), "none");
});

test("faster means wider", () => {
  assert.ok(zoomForSpeed(80) < zoomForSpeed(40));
  assert.ok(zoomForSpeed(40) < zoomForSpeed(5));
  assert.equal(zoomForSpeed(null), 17);
});
