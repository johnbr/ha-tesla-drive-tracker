import assert from "node:assert/strict";
import { test } from "node:test";
import { DEFAULTS, parseConfig, safeImage } from "../../src/config.ts";

test("an empty config gets the defaults", () => {
  assert.deepEqual(parseConfig({ type: "custom:tesla-drive-tracker-card" }), DEFAULTS);
});

test("layout keys are not options", () => {
  assert.doesNotThrow(() => parseConfig({ view_layout: { "grid-area": "a" }, card_mod: {} }));
});

test("a typo throws rather than becoming the default", () => {
  assert.throws(() => parseConfig({ folow: "car" }), /Unknown option: folow/);
});

test("a wrong value throws", () => {
  assert.throws(() => parseConfig({ follow: "sometimes" }), /follow must be one of/);
  assert.throws(() => parseConfig({ height: 10 }), /height must be a number/);
  assert.throws(() => parseConfig({ route_color: "blue" }), /route_color must be a colour/);
  assert.throws(() => parseConfig({ hud_fields: [] }), /hud_fields/);
  assert.throws(() => parseConfig({ hud_fields: ["weather"] }), /hud_fields/);
});

test("a colour can't carry markup", () => {
  assert.throws(() => parseConfig({ color: '"><script>' }));
  assert.equal(parseConfig({ color: "SteelGrey" }).color, "SteelGrey");
  assert.equal(parseConfig({ color: "#112233" }).color, "#112233");
});

test("pictures are this Home Assistant's own or https", () => {
  assert.ok(safeImage("/local/car.png"));
  assert.ok(safeImage("https://example.com/car.png"));
  assert.ok(!safeImage("http://example.com/car.png"));
  assert.ok(!safeImage("//example.com/car.png"));
  assert.ok(!safeImage("/\\example.com/car.png"));
  assert.ok(!safeImage("javascript:alert(1)"));
  assert.ok(!safeImage("data:image/svg+xml,<svg/>"));
  assert.throws(() => parseConfig({ image: "javascript:alert(1)" }), /image must be/);
});
