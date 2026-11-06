import assert from "node:assert/strict";
import { test } from "node:test";
import { UNKNOWN_PAINT, outlineColor, paintColor, roofColor } from "../../src/paint.ts";

test("the car's paint name becomes a colour", () => {
  assert.equal(paintColor("auto", "SteelGrey"), "#6d7276");
  assert.equal(paintColor("auto", "pearl_white"), "#eff0ef");
});

test("the card's choice beats the car", () => {
  assert.equal(paintColor("#112233", "SteelGrey"), "#112233");
  assert.equal(paintColor("DeepBlue", "SteelGrey"), "#1f3a6e");
});

test("an unknown paint is neutral, never passed through", () => {
  assert.equal(paintColor("auto", null), UNKNOWN_PAINT);
  assert.equal(paintColor("auto", '"><script>'), UNKNOWN_PAINT);
});

test("a roof reported as None is glass", () => {
  assert.notEqual(roofColor("auto", "None", "#6d7276"), "#6d7276");
  assert.equal(roofColor("auto", "Body", "#6d7276"), "#6d7276");
  assert.equal(roofColor("body", "None", "#6d7276"), "#6d7276");
});

test("a light car gets a dark line and a dark car a lighter one", () => {
  assert.equal(outlineColor("#eff0ef"), "#1c1e21");
  assert.equal(outlineColor("#17181a"), "#55595e");
});
