/**
 * What the map should do with its view.
 *
 * Import-free. `auto` follows the car while it drives with nowhere set, and
 * otherwise shows the whole trip, so a route keeps the car and the pin in view.
 * Touching the map hands it to the user until `recenter_after` passes.
 */

export type FollowMode = "auto" | "car" | "fit" | "off";
export type ViewAction = "car" | "fit" | "none";

export function viewAction(
  follow: FollowMode,
  driving: boolean,
  userAt: number | null,
  recenterAfter: number,
  now: number,
  destination = false
): ViewAction {
  if (follow === "off") return "none";
  if (userAt !== null && (recenterAfter === 0 || now - userAt < recenterAfter)) return "none";
  if (follow === "fit") return "fit";
  if (follow === "car") return "car";
  return driving && !destination ? "car" : "fit";
}

/** A wider view at speed, so the road ahead stays on screen. */
export function zoomForSpeed(mph: number | null): number {
  const speed = mph ?? 0;
  if (speed < 25) return 17;
  if (speed < 50) return 16;
  if (speed < 75) return 15;
  return 14;
}
