import assert from "node:assert/strict";
import { test } from "node:test";
import { arrowSvg, carSvg, destinationSvg, dotSvg } from "../../src/markers.ts";

const look = { paint: "#6d7276", roof: "#20262c", outline: "#1c1e21" };

test("each model has its own drawing", () => {
  const drawings = new Set(["s", "3", "x", "y", "cybertruck"].map((model) => carSvg(model, look)));
  assert.equal(drawings.size, 5);
});

test("an unknown model still draws a car", () => {
  assert.equal(carSvg("roadster", look), carSvg("s", look));
  assert.equal(carSvg(null, look), carSvg("s", look));
});

test("the paint reaches the drawing", () => {
  assert.ok(carSvg("s", look).includes('fill="#6d7276"'));
  assert.ok(arrowSvg(look).includes('fill="#6d7276"'));
  assert.ok(dotSvg(look).includes('fill="#6d7276"'));
});

test("mirrored parts are mirrored", () => {
  const svg = carSvg("3", look);
  assert.ok(svg.includes('cx="8.5"') && svg.includes('cx="55.5"'));
});

test("the drawings are well formed", () => {
  for (const svg of [carSvg("x", look), arrowSvg(look), dotSvg(look), destinationSvg()]) {
    assert.match(svg, /^<svg .*<\/svg>$/);
    assert.ok(!svg.includes("NaN"));
  }
});
