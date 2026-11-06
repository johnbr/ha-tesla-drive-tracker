/**
 * Everything the card draws on a map.
 *
 * `MapSurface` is what the card talks to, so a second map provider only has to
 * implement this. `HaSurface` draws on `ha-map`'s engine, on MapLibre and on the
 * Leaflet fallback alike. It belongs to one engine instance: when `ha-map`
 * replaces its engine, every handle here is dead and the card builds a new one.
 */

import {
  moveMarker,
  raiseMarker,
  type EngineLatLng,
  type EngineMarkerHandle,
  type EnginePathHandle,
  type MapEngine,
} from "./engine";
import type { LatLng } from "./geo";

export interface MarkerArt {
  /** Trusted markup from markers.ts. */
  svg?: string;
  /** A picture already checked by `safeImage`. */
  image?: string;
  width: number;
  height: number;
  /** Which way the art's nose points, in degrees clockwise from up. */
  nose: number;
}

export interface ZoneCircle {
  center: LatLng;
  radius: number;
  color: string;
}

export interface MapSurface {
  setCarArt(art: MarkerArt): void;
  moveCar(position: LatLng, heading: number | null): void;
  removeCar(): void;
  setDestination(position: LatLng | null, name: string | null, svg: string): void;
  setRoute(points: LatLng[] | null, color: string): void;
  setTrail(points: LatLng[] | null, color: string): void;
  setZones(zones: ZoneCircle[]): void;
  destroy(): void;
  abandon(): void;
}

const PIN_SIZE: [number, number] = [28, 37];

/** What a map must offer, so a future change shows an error, not an empty map. */
export function engineProblem(engine: MapEngine): string | null {
  const missing = (["addMarker", "addPath"] as const).filter((name) => typeof engine[name] !== "function");
  return missing.length ? `The map has no ${missing.join(" or ")}` : null;
}

export class HaSurface implements MapSurface {
  private car?: { handle: EngineMarkerHandle; element: HTMLElement; inner: HTMLElement; nose: number };
  private carAt?: LatLng;
  private art?: MarkerArt;
  private heading: number | null = null;
  private pin?: { handle: EngineMarkerHandle; element: HTMLElement };
  private pinAt?: LatLng;
  private route?: EnginePathHandle;
  private trail?: EnginePathHandle;
  private zones: { remove(): void }[] = [];

  constructor(readonly engine: MapEngine) {}

  setCarArt(art: MarkerArt): void {
    this.art = art;
    if (this.car) this.removeCar();
    if (this.carAt) this.moveCar(this.carAt, this.heading);
  }

  moveCar(position: LatLng, heading: number | null): void {
    this.carAt = position;
    this.heading = heading;
    if (!this.car) this.addCar(position);
    const car = this.car;
    if (!car) return;
    moveMarker(car.handle, position as EngineLatLng);
    const bearing = this.engine._maplibre?.getBearing?.() ?? 0;
    car.inner.style.transform = `rotate(${(heading ?? 0) - car.nose - bearing}deg)`;
  }

  private addCar(position: LatLng): void {
    const art = this.art;
    if (!art) return;
    const element = document.createElement("div");
    const inner = document.createElement("div");
    inner.className = "tdt-car";
    inner.style.cssText = `width:${art.width}px;height:${art.height}px;will-change:transform`;
    if (art.image) {
      const image = document.createElement("img");
      image.src = art.image;
      image.alt = "";
      image.style.cssText = "width:100%;height:100%;object-fit:contain;display:block";
      inner.append(image);
    } else if (art.svg) {
      inner.innerHTML = art.svg;
    }
    element.append(inner);
    // Non-interactive, so a drag that starts on the car still pans the map.
    const handle = this.engine.addMarker(element, position as EngineLatLng, {
      size: [art.width, art.height],
      interactive: false,
      focusable: false,
      raised: true,
    });
    raiseMarker(handle, element, 1, true);
    this.car = { handle, element, inner, nose: art.nose };
  }

  removeCar(): void {
    this.car?.handle.remove();
    this.car = undefined;
  }

  setDestination(position: LatLng | null, name: string | null, svg: string): void {
    const moved =
      position === null || !this.pinAt || position[0] !== this.pinAt[0] || position[1] !== this.pinAt[1];
    if (moved) {
      this.pin?.handle.remove();
      this.pin = undefined;
      this.pinAt = undefined;
    }
    if (position === null) return;
    if (!this.pin) {
      const element = document.createElement("div");
      element.innerHTML = svg;
      element.style.cssText = `width:${PIN_SIZE[0]}px;height:${PIN_SIZE[1]}px`;
      const handle = this.engine.addMarker(element, position as EngineLatLng, {
        size: PIN_SIZE,
        anchor: [PIN_SIZE[0] / 2, PIN_SIZE[1]],
        interactive: false,
        focusable: false,
      });
      raiseMarker(handle, element, 0, false);
      this.pin = { handle, element };
      this.pinAt = position;
    }
    // Set as a property, never as markup: the name comes from the car.
    this.pin.element.title = name ?? "";
  }

  setRoute(points: LatLng[] | null, color: string): void {
    this.route = this.drawLine(this.route, points, color, 0.9);
  }

  setTrail(points: LatLng[] | null, color: string): void {
    this.trail = this.drawLine(this.trail, points, color, 0.75);
  }

  private drawLine(
    handle: EnginePathHandle | undefined,
    points: LatLng[] | null,
    color: string,
    opacity: number
  ): EnginePathHandle | undefined {
    if (!points || points.length < 2) {
      handle?.remove();
      return undefined;
    }
    const spec = { color, segments: [{ points: points as EngineLatLng[], opacity }], markers: [] };
    if (handle) {
      handle.update(spec);
      return handle;
    }
    return this.engine.addPath(spec);
  }

  setZones(zones: ZoneCircle[]): void {
    this.zones.forEach((zone) => zone.remove());
    this.zones = zones.flatMap((zone) => {
      const circle = this.engine.addCircle?.(zone.center as EngineLatLng, {
        radius: zone.radius,
        color: zone.color,
        outline: false,
      });
      return circle ? [circle] : [];
    });
  }

  /** Take everything off a map that is staying. */
  destroy(): void {
    this.removeCar();
    this.setDestination(null, null, "");
    this.setRoute(null, "");
    this.setTrail(null, "");
    this.setZones([]);
  }

  /** Forget everything, because the engine has already gone. */
  abandon(): void {
    this.car = undefined;
    this.pin = undefined;
    this.pinAt = undefined;
    this.route = undefined;
    this.trail = undefined;
    this.zones = [];
  }
}
