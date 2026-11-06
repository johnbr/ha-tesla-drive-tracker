/**
 * Where to draw the car on this frame.
 *
 * Import-free apart from a type: the prediction itself is passed in, so this file
 * stays runnable under `node --test`.
 *
 * A new fix rarely lands exactly where the car was predicted to be. Jumping there
 * would show every correction, so the gap is kept as an offset that fades over a
 * second while the prediction carries on from the fix. Each frame draws from the
 * clock, so a backgrounded tab comes back to the present rather than replaying
 * what it missed.
 */

import type { Fix, LatLng } from "./geo";

export const CORRECTION_MS = 1000;
const TURN_MS = 400;

type Predict = (fix: Fix, route: LatLng[] | null, seconds: number) => LatLng;
type Turn = (from: number, to: number, part: number) => number;

export interface Drawn {
  position: LatLng;
  heading: number | null;
}

export class CarMotion {
  private fix?: Fix;
  private fixAt = 0;
  private route: LatLng[] | null = null;
  private offset: LatLng = [0, 0];
  private fromHeading: number | null = null;

  private readonly predict: Predict;
  private readonly turn: Turn;
  private readonly smooth: () => boolean;

  constructor(predict: Predict, turn: Turn, smooth: () => boolean) {
    this.predict = predict;
    this.turn = turn;
    this.smooth = smooth;
  }

  /** Take a new fix, holding on to wherever the car is currently drawn. */
  update(fix: Fix, route: LatLng[] | null, now: number): void {
    const drawn = this.fix ? this.at(now) : undefined;
    this.fix = fix;
    this.fixAt = now;
    this.route = route;
    if (drawn && this.smooth()) {
      this.offset = [drawn.position[0] - fix.position[0], drawn.position[1] - fix.position[1]];
      this.fromHeading = drawn.heading;
    } else {
      this.offset = [0, 0];
      this.fromHeading = fix.heading;
    }
  }

  setRoute(route: LatLng[] | null): void {
    this.route = route;
  }

  /** Whether frames are still changing anything. */
  moving(now: number): boolean {
    return this.fix !== undefined && this.smooth() && ((this.fix.speed ?? 0) > 0 || now - this.fixAt < CORRECTION_MS);
  }

  at(now: number): Drawn {
    const fix = this.fix;
    if (!fix) return { position: [0, 0], heading: null };
    if (!this.smooth()) return { position: fix.position, heading: fix.heading };
    const age = now - this.fixAt;
    const fade = Math.max(0, 1 - age / CORRECTION_MS);
    const ahead = this.predict(fix, this.route, age / 1000);
    const part = Math.min(1, age / TURN_MS);
    const heading =
      fix.heading === null || this.fromHeading === null ? fix.heading : this.turn(this.fromHeading, fix.heading, part);
    return { position: [ahead[0] + this.offset[0] * fade, ahead[1] + this.offset[1] * fade], heading };
  }
}
