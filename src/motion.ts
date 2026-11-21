/**
 * Where to draw the car on this frame.
 *
 * Import-free apart from types: the geometry is passed in, so this file stays
 * runnable under `node --test`.
 *
 * A new fix rarely lands exactly where the car was predicted to be. Jumping there
 * would show every correction, so the gap is kept as an offset that fades over two
 * seconds while the prediction carries on from the fix. Fading for longer than the
 * fixes are apart, when they come every second, evens out their GPS noise rather
 * than chasing it from side to side. Each frame draws from the
 * clock, so a backgrounded tab comes back to the present rather than replaying
 * what it missed.
 *
 * A car looks as if it slides when it moves somewhere its nose doesn't point, and
 * worst when it backs up. Replaying recorded drives showed that happening mostly
 * as the car stopped: its speed comes only every five seconds or so, so it was
 * drawn running on past where it stopped and then backing up to its fixes. So:
 *
 * - The car is paced by the fresher of its reported speed and its speed between
 *   its last two fixes, and a car braking between fixes is predicted to keep
 *   braking.
 * - A fix that lands behind the drawn car is let catch up by slowing the car,
 *   for as long as that takes, rather than by backing the car up to it.
 */

import type { Fix, LatLng } from "./geo";

export const CORRECTION_MS = 2000;
/** The longest a correction is spread over, so the car is not drawn off its fixes for long. */
export const MAX_CORRECTION_MS = 8000;
/** The share of its pace the car keeps while a fix behind it catches up. */
const KEEP_PACE = 0.3;
const TURN_MS = 400;
/** Fixes closer together or further apart than this don't pace the car. */
const PACE_MIN_MS = 1000;
const PACE_MAX_MS = 6000;
/** The hardest braking carried on from the fixes, in miles an hour lost each second. */
const MAX_SLOWING = 4;
const METRES_PER_SECOND_PER_MPH = 0.44704;

/** What the motion needs from geo.ts, passed in so this file needs no imports. */
export interface Geometry {
  predict(fix: Fix, route: LatLng[] | null, seconds: number): LatLng;
  turnTowards(from: number, to: number, part: number): number;
  metres(a: LatLng, b: LatLng): number;
  bearing(a: LatLng, b: LatLng): number;
  /** How far past the last position the car is predicted. */
  PREDICT_MAX_SECONDS: number;
  /** Below this the prediction holds the car still. */
  PREDICT_MIN_MPH: number;
  /** How long after a position the car is predicted along its heading before its route. */
  ROUTE_AFTER_SECONDS: number;
}

export interface Drawn {
  position: LatLng;
  heading: number | null;
}

export class CarMotion {
  /** What the car is predicted on from: the last fix, re-aimed by any speed or heading since. */
  private fix?: Fix;
  private fixAt = 0;
  /** The last position as reported, and when it came. */
  private position?: LatLng;
  private positionAt = 0;
  /** The speed and heading as reported, which the prediction may have moved on from. */
  private reported: { speed: number | null; heading: number | null } = { speed: null, heading: null };
  private speedAt = -Infinity;
  /** The speed between the last two fixes, as of halfway between them. */
  private between?: { speed: number; at: number };
  private route: LatLng[] | null = null;
  private onRoute = false;
  private offset: LatLng = [0, 0];
  private correctionAt = 0;
  private correctionMs = CORRECTION_MS;
  private fromHeading: number | null = null;
  private turnAt = 0;

  private readonly geo: Geometry;
  private readonly smooth: () => boolean;

  constructor(geo: Geometry, smooth: () => boolean) {
    this.geo = geo;
    this.smooth = smooth;
  }

  /** Take a new fix, holding on to wherever the car is currently drawn. */
  update(fix: Fix, route: LatLng[] | null, now: number): void {
    const drawn = this.fix ? this.at(now) : undefined;
    if (fix.speed !== this.reported.speed) this.speedAt = now;
    this.reported = { speed: fix.speed, heading: fix.heading };
    this.fix = this.paced(fix, now);
    this.fixAt = now;
    this.position = fix.position;
    this.positionAt = now;
    this.correctionAt = now;
    this.turnAt = now;
    this.route = route;
    this.onRoute = false;
    if (drawn && this.smooth()) {
      this.offset = [drawn.position[0] - fix.position[0], drawn.position[1] - fix.position[1]];
      this.fromHeading = drawn.heading;
      this.correctionMs = this.spread(drawn.position);
    } else {
      this.offset = [0, 0];
      this.fromHeading = fix.heading;
      this.correctionMs = CORRECTION_MS;
    }
  }

  /**
   * Take a new speed or heading that arrived without a new position: the car's
   * signals come one at a time, speed every five seconds or so and heading in
   * between positions. The prediction carries on from where it has got to, aimed
   * and paced by the new values, and the correction still fading toward the last
   * fix carries on fading. The cap on predicting still counts from the last
   * position.
   */
  carryOn(changes: { speed?: number | null; heading?: number | null }, now: number): void {
    const fix = this.fix;
    if (!fix) return;
    const speed = changes.speed === undefined ? this.reported.speed : changes.speed;
    const heading = changes.heading === undefined ? this.reported.heading : changes.heading;
    const newSpeed = speed !== this.reported.speed;
    if (!newSpeed && heading === this.reported.heading) return;
    const drawn = this.at(now);
    const position = this.smooth() ? this.ahead(now) : fix.position;
    this.fix = { position, heading, speed: newSpeed ? speed : this.paceAt(now), slowing: fix.slowing };
    this.fixAt = now;
    if (newSpeed) this.speedAt = now;
    if (heading !== this.reported.heading) {
      this.fromHeading = drawn.heading;
      this.turnAt = now;
    }
    this.reported = { speed, heading };
  }

  setRoute(route: LatLng[] | null): void {
    this.route = route;
  }

  /** Whether frames are still changing anything. */
  moving(now: number): boolean {
    return (
      this.fix !== undefined &&
      this.smooth() &&
      ((this.paceAt(now) ?? 0) >= this.geo.PREDICT_MIN_MPH || now - this.correctionAt < this.correctionMs)
    );
  }

  at(now: number): Drawn {
    if (!this.fix) return { position: [0, 0], heading: null };
    if (!this.smooth()) return { position: this.fix.position, heading: this.fix.heading };
    const fade = Math.max(0, 1 - (now - this.correctionAt) / this.correctionMs);
    const ahead = this.ahead(now);
    const target = this.fix.heading;
    const part = Math.min(1, (now - this.turnAt) / TURN_MS);
    const heading =
      target === null || this.fromHeading === null ? target : this.geo.turnTowards(this.fromHeading, target, part);
    return { position: [ahead[0] + this.offset[0] * fade, ahead[1] + this.offset[1] * fade], heading };
  }

  /**
   * Where the prediction has got to, without the fading correction. Once a
   * position is overdue the route predicts the car better than its heading, so
   * from then on it carries on along the route from where the heading got it to.
   */
  private ahead(now: number): LatLng {
    const handover = this.positionAt + this.geo.ROUTE_AFTER_SECONDS * 1000;
    if (this.route && !this.onRoute && now > handover) {
      this.fix = { ...(this.fix as Fix), position: this.predicted(handover), speed: this.paceAt(handover) };
      this.fixAt = handover;
      this.onRoute = true;
    }
    return this.predicted(now);
  }

  private predicted(now: number): LatLng {
    const left = this.geo.PREDICT_MAX_SECONDS - (this.fixAt - this.positionAt) / 1000;
    const seconds = Math.min((now - this.fixAt) / 1000, Math.max(0, left));
    return this.geo.predict(this.fix as Fix, this.onRoute ? this.route : null, seconds);
  }

  /** The speed predicted for `now`, which a braking car has lost some of since the fix. */
  private paceAt(now: number): number | null {
    const { speed, slowing } = this.fix as Fix;
    if (speed === null || !slowing) return speed;
    return Math.max(0, speed - (slowing * Math.max(0, now - this.fixAt)) / 1000);
  }

  /**
   * The fix, paced by the fresher of its reported speed and its speed since the
   * last fix, which is its speed halfway between the two; and braking on if that
   * has fallen since the fix before.
   */
  private paced(fix: Fix, now: number): Fix {
    const gap = now - this.positionAt;
    if (!this.position || gap < PACE_MIN_MS || gap > PACE_MAX_MS) {
      this.between = undefined;
      return fix;
    }
    const speed = this.geo.metres(this.position, fix.position) / (gap / 1000) / METRES_PER_SECOND_PER_MPH;
    const at = now - gap / 2;
    const before = this.between;
    this.between = { speed, at };
    const slowing =
      before && at - before.at <= PACE_MAX_MS
        ? Math.min(MAX_SLOWING, Math.max(0, (before.speed - speed) / ((at - before.at) / 1000)))
        : 0;
    if (this.speedAt > at) return { ...fix, slowing };
    return { ...fix, speed: Math.max(0, speed - (slowing * (now - at)) / 1000), slowing };
  }

  /**
   * How long to spread the correction to a new fix over: if the fix is behind
   * the drawn car, long enough that the car slows to let it catch up rather than
   * backing up to it.
   */
  private spread(drawn: LatLng): number {
    const fix = this.fix as Fix;
    if (fix.heading === null) return CORRECTION_MS;
    const off = ((this.geo.bearing(fix.position, drawn) - fix.heading) * Math.PI) / 180;
    const ahead = this.geo.metres(fix.position, drawn) * Math.cos(off);
    if (ahead <= 0) return CORRECTION_MS;
    const speed = fix.speed ?? 0;
    const pace = speed < this.geo.PREDICT_MIN_MPH ? 0 : speed * METRES_PER_SECOND_PER_MPH * (1 - KEEP_PACE);
    return Math.min(MAX_CORRECTION_MS, Math.max(CORRECTION_MS, (ahead / pace) * 1000));
  }
}
