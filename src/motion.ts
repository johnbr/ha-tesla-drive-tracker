/**
 * Where to draw the car on this frame.
 *
 * Import-free apart from a type: the prediction and its cap are passed in, so
 * this file stays runnable under `node --test`.
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
  private positionAt = 0;
  private route: LatLng[] | null = null;
  private offset: LatLng = [0, 0];
  private correctionAt = 0;
  private fromHeading: number | null = null;
  private turnAt = 0;

  private readonly predict: Predict;
  private readonly turn: Turn;
  private readonly smooth: () => boolean;
  private readonly maxSeconds: number;

  /** `maxSeconds` caps how far past the last position the car is predicted. */
  constructor(predict: Predict, turn: Turn, smooth: () => boolean, maxSeconds: number) {
    this.predict = predict;
    this.turn = turn;
    this.smooth = smooth;
    this.maxSeconds = maxSeconds;
  }

  /** Take a new fix, holding on to wherever the car is currently drawn. */
  update(fix: Fix, route: LatLng[] | null, now: number): void {
    const drawn = this.fix ? this.at(now) : undefined;
    this.fix = fix;
    this.fixAt = now;
    this.positionAt = now;
    this.correctionAt = now;
    this.turnAt = now;
    this.route = route;
    if (drawn && this.smooth()) {
      this.offset = [drawn.position[0] - fix.position[0], drawn.position[1] - fix.position[1]];
      this.fromHeading = drawn.heading;
    } else {
      this.offset = [0, 0];
      this.fromHeading = fix.heading;
    }
  }

  /**
   * Take a new speed or heading that arrived without a new position: the car's
   * signals come one at a time, speed about 30 ms after each position and
   * heading in between. The prediction carries on from where it has got to,
   * aimed and paced by the new values, and the correction still fading toward
   * the last fix carries on fading. The cap on predicting still counts from the
   * last position.
   */
  carryOn(changes: { speed?: number | null; heading?: number | null }, now: number): void {
    const fix = this.fix;
    if (!fix) return;
    const speed = changes.speed === undefined ? fix.speed : changes.speed;
    const heading = changes.heading === undefined ? fix.heading : changes.heading;
    if (speed === fix.speed && heading === fix.heading) return;
    const drawn = this.at(now);
    this.fix = { position: this.ahead(now), heading, speed };
    this.fixAt = now;
    if (heading !== fix.heading) {
      this.fromHeading = drawn.heading;
      this.turnAt = now;
    }
  }

  setRoute(route: LatLng[] | null): void {
    this.route = route;
  }

  /** Whether frames are still changing anything. */
  moving(now: number): boolean {
    return (
      this.fix !== undefined && this.smooth() && ((this.fix.speed ?? 0) > 0 || now - this.correctionAt < CORRECTION_MS)
    );
  }

  at(now: number): Drawn {
    const fix = this.fix;
    if (!fix) return { position: [0, 0], heading: null };
    if (!this.smooth()) return { position: fix.position, heading: fix.heading };
    const fade = Math.max(0, 1 - (now - this.correctionAt) / CORRECTION_MS);
    const ahead = this.ahead(now);
    const part = Math.min(1, (now - this.turnAt) / TURN_MS);
    const heading =
      fix.heading === null || this.fromHeading === null ? fix.heading : this.turn(this.fromHeading, fix.heading, part);
    return { position: [ahead[0] + this.offset[0] * fade, ahead[1] + this.offset[1] * fade], heading };
  }

  /** Where the prediction has got to, without the fading correction. */
  private ahead(now: number): LatLng {
    const fix = this.fix as Fix;
    const left = this.maxSeconds - (this.fixAt - this.positionAt) / 1000;
    return this.predict(fix, this.route, Math.min((now - this.fixAt) / 1000, Math.max(0, left)));
  }
}
