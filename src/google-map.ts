/**
 * Google Maps as a second map provider, for `map_provider: google`.
 *
 * `ha-map` needs no key and has no satellite or traffic; Google has both, at the
 * cost of an API key the user brings. The card talks to it through the same
 * `MapSurface` as `ha-map`, plus a `MapView` for the camera.
 *
 * Facts that shape the code:
 *
 * 1. **The script is loaded once per page, and shared.** Another card (such as
 *    google-map-card) may already have loaded it, possibly with its own key.
 *    Loading it twice breaks both, so an existing `google.maps` is used as it is.
 *
 * 2. **`loading=async` fills `google.maps` lazily.** Classes such as `Map` only
 *    appear once `importLibrary` resolves, so they're read from what it returns,
 *    falling back to the namespace for an old-style load by someone else.
 *
 * 3. **Markers are `OverlayView`s holding elements we own**, not `Marker`s:
 *    moving one is a transform, so the car can glide every animation frame
 *    without rebuilding anything, and an SVG is drawn as it is. They go in the
 *    `overlayLayer` pane, which takes no pointer events, so a drag that starts
 *    on the car still pans the map.
 *
 * 4. **Zoom levels match Leaflet's**, which is the scale `ha-map` reports, so the
 *    card's speed zooms mean the same on both.
 *
 * 5. **Each new `google.maps.Map` is a billed map load.** The card keeps one per
 *    element and reuses it across reconnects and config changes.
 *
 * Only the few calls used here are typed, rather than pulling in @types.
 */

import type { LatLng } from "./geo";
import type { MapSurface, MapView, MarkerArt, ZoneCircle } from "./surface";

interface GLatLngLiteral {
  lat: number;
  lng: number;
}

interface GMap {
  fitBounds(bounds: { north: number; south: number; east: number; west: number }, padding?: number): void;
  panTo(latlng: GLatLngLiteral): void;
  setCenter(latlng: GLatLngLiteral): void;
  getCenter(): { lat(): number; lng(): number } | undefined;
  setZoom(zoom: number): void;
  getZoom(): number | undefined;
  getHeading?(): number | undefined;
  setMapTypeId(type: string): void;
  setOptions(options: Record<string, unknown>): void;
}

interface GOverlay {
  setMap(map: GMap | null): void;
  getPanes(): { overlayLayer: HTMLElement } | null;
  getProjection(): { fromLatLngToDivPixel(latlng: GLatLngLiteral): { x: number; y: number } | null } | null;
}

interface GShape {
  setMap(map: GMap | null): void;
  setOptions(options: Record<string, unknown>): void;
}

export interface GoogleMaps {
  Map: new (element: HTMLElement, options: Record<string, unknown>) => GMap;
  OverlayView: new () => GOverlay;
  Polyline: new (options: Record<string, unknown>) => GShape;
  Circle: new (options: Record<string, unknown>) => GShape;
  TrafficLayer: new () => GShape;
  event: { addListenerOnce(target: unknown, name: string, handler: () => void): unknown };
}

interface GoogleNamespace {
  maps?: Partial<GoogleMaps> & { importLibrary?(name: string): Promise<Record<string, unknown>> };
}

declare global {
  interface Window {
    google?: GoogleNamespace;
  }
}

const LOAD_TIMEOUT_MS = 15_000;
const CALLBACK = "__teslaDriveTrackerGoogleReady";

let loading: Promise<GoogleMaps | undefined> | undefined;

/** The Maps API, loading it with this key if nothing on the page has yet. */
export function loadGoogleMaps(key: string): Promise<GoogleMaps | undefined> {
  loading ??= (async () => {
    if (!window.google?.maps) {
      const ready = new Promise<boolean>((resolve) => {
        (window as unknown as Record<string, unknown>)[CALLBACK] = () => resolve(true);
        const script = document.createElement("script");
        const params = new URLSearchParams({ key, v: "weekly", loading: "async", callback: CALLBACK });
        script.src = `https://maps.googleapis.com/maps/api/js?${params}`;
        script.async = true;
        script.onerror = () => resolve(false);
        document.head.append(script);
        setTimeout(() => resolve(false), LOAD_TIMEOUT_MS);
      });
      if (!(await ready)) return undefined;
    }
    const maps = window.google?.maps;
    if (!maps) return undefined;
    // See fact 2.
    const libraries = maps.importLibrary
      ? Object.assign({}, ...(await Promise.all(["core", "maps"].map((name) => maps.importLibrary!(name)))))
      : {};
    const api = { ...maps, ...libraries } as Partial<GoogleMaps>;
    return api.Map && api.OverlayView && api.Polyline && api.Circle && api.event ? (api as GoogleMaps) : undefined;
  })();
  // A failed load can be retried, say after the key is fixed.
  void loading.then((maps) => {
    if (!maps) loading = undefined;
  });
  return loading;
}

export interface GoogleOptions {
  mapType: string;
  traffic: boolean;
  dark: boolean;
}

const literal = ([lat, lng]: LatLng): GLatLngLiteral => ({ lat, lng });

/** One Google map in one element, and the camera calls the card makes on it. */
export class GoogleView implements MapView {
  readonly map: GMap;

  constructor(
    readonly maps: GoogleMaps,
    readonly host: HTMLElement,
    options: GoogleOptions
  ) {
    this.map = new maps.Map(host, {
      center: { lat: 0, lng: 0 },
      zoom: 3,
      mapTypeId: options.mapType,
      // Only takes effect when the map is made.
      colorScheme: options.dark ? "DARK" : "LIGHT",
      disableDefaultUI: true,
      zoomControl: true,
      gestureHandling: "greedy",
      clickableIcons: false,
      keyboardShortcuts: false,
    });
  }

  /** Leaflet's `pad` is a fraction of the box added on each side; `zoom` is a ceiling. */
  fitBounds(latlngs: LatLng[], options: { pad?: number; zoom?: number } = {}): void {
    if (!latlngs.length) return;
    const lats = latlngs.map(([lat]) => lat);
    const lngs = latlngs.map(([, lng]) => lng);
    const [south, north, west, east] = [Math.min(...lats), Math.max(...lats), Math.min(...lngs), Math.max(...lngs)];
    if (south === north && west === east) {
      this.map.setCenter({ lat: south, lng: west });
      this.map.setZoom(options.zoom ?? 18);
      return;
    }
    const pad = options.pad ?? 0.5;
    const dLat = (north - south) * pad;
    const dLng = (east - west) * pad;
    this.map.fitBounds({ south: south - dLat, north: north + dLat, west: west - dLng, east: east + dLng }, 0);
    const ceiling = options.zoom;
    if (ceiling !== undefined) {
      this.maps.event.addListenerOnce(this.map, "bounds_changed", () => {
        if ((this.map.getZoom() ?? 0) > ceiling) this.map.setZoom(ceiling);
      });
    }
  }

  panTo(latlng: LatLng): void {
    this.map.panTo(literal(latlng));
  }

  getView(): { center: [number, number]; zoom: number } | undefined {
    const center = this.map.getCenter();
    const zoom = this.map.getZoom();
    return center && zoom !== undefined ? { center: [center.lat(), center.lng()], zoom } : undefined;
  }
}

interface Overlay extends GOverlay {
  readonly element: HTMLElement;
  moveTo(position: LatLng): void;
}

/** An element pinned to a place, its anchor in pixels from its top-left. */
function overlayClass(maps: GoogleMaps): new (element: HTMLElement, anchor: [number, number], zIndex: number) => Overlay {
  return class extends maps.OverlayView implements Overlay {
    private at?: LatLng;

    constructor(
      readonly element: HTMLElement,
      private readonly anchor: [number, number],
      zIndex: number
    ) {
      super();
      element.style.position = "absolute";
      element.style.left = "0";
      element.style.top = "0";
      element.style.zIndex = String(zIndex);
    }

    onAdd(): void {
      this.getPanes()?.overlayLayer.append(this.element);
    }

    draw(): void {
      const point = this.at && this.getProjection()?.fromLatLngToDivPixel(literal(this.at));
      if (!point) return;
      this.element.style.transform = `translate(${point.x - this.anchor[0]}px, ${point.y - this.anchor[1]}px)`;
    }

    onRemove(): void {
      this.element.remove();
    }

    moveTo(position: LatLng): void {
      this.at = position;
      this.draw();
    }
  };
}

const PIN_SIZE: [number, number] = [28, 37];

/** A white casing under the route keeps it readable on satellite imagery. */
const ROUTE_CASING = { strokeColor: "#ffffff", strokeOpacity: 0.9, strokeWeight: 8, zIndex: 1 };

export class GoogleSurface implements MapSurface {
  private readonly Overlay: ReturnType<typeof overlayClass>;
  private readonly trafficLayer?: GShape;
  private car?: { overlay: Overlay; inner: HTMLElement; nose: number };
  private carAt?: LatLng;
  private art?: MarkerArt;
  private heading: number | null = null;
  private pin?: Overlay;
  private pinAt?: LatLng;
  private route: GShape[] = [];
  private trail: GShape[] = [];
  private zones: GShape[] = [];

  constructor(
    readonly view: GoogleView,
    options: GoogleOptions
  ) {
    this.Overlay = overlayClass(view.maps);
    view.map.setMapTypeId(options.mapType);
    if (options.traffic && view.maps.TrafficLayer) {
      this.trafficLayer = new view.maps.TrafficLayer();
      this.trafficLayer.setMap(view.map);
    }
  }

  setCarArt(art: MarkerArt): void {
    this.art = art;
    if (this.car) this.removeCar();
    if (this.carAt) this.moveCar(this.carAt, this.heading);
  }

  moveCar(position: LatLng, heading: number | null): void {
    this.carAt = position;
    this.heading = heading;
    if (!this.car) this.addCar();
    const car = this.car;
    if (!car) return;
    car.overlay.moveTo(position);
    const bearing = this.view.map.getHeading?.() ?? 0;
    car.inner.style.transform = `rotate(${(heading ?? 0) - car.nose - bearing}deg)`;
  }

  private addCar(): void {
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
    const overlay = new this.Overlay(element, [art.width / 2, art.height / 2], 2);
    overlay.setMap(this.view.map);
    this.car = { overlay, inner, nose: art.nose };
  }

  removeCar(): void {
    this.car?.overlay.setMap(null);
    this.car = undefined;
  }

  setDestination(position: LatLng | null, name: string | null, svg: string): void {
    const moved =
      position === null || !this.pinAt || position[0] !== this.pinAt[0] || position[1] !== this.pinAt[1];
    if (moved) {
      this.pin?.setMap(null);
      this.pin = undefined;
      this.pinAt = undefined;
    }
    if (position === null) return;
    if (!this.pin) {
      const element = document.createElement("div");
      element.innerHTML = svg;
      element.style.width = `${PIN_SIZE[0]}px`;
      element.style.height = `${PIN_SIZE[1]}px`;
      this.pin = new this.Overlay(element, [PIN_SIZE[0] / 2, PIN_SIZE[1]], 1);
      this.pin.setMap(this.view.map);
      this.pin.moveTo(position);
      this.pinAt = position;
    }
    // Set as a property, never as markup: the name comes from the car.
    this.pin.element.title = name ?? "";
  }

  setRoute(points: LatLng[] | null, color: string): void {
    this.route = this.drawLine(this.route, points, [
      ROUTE_CASING,
      { strokeColor: color, strokeOpacity: 1, strokeWeight: 5, zIndex: 2 },
    ]);
  }

  setTrail(points: LatLng[] | null, color: string): void {
    this.trail = this.drawLine(this.trail, points, [{ strokeColor: color, strokeOpacity: 0.75, strokeWeight: 4, zIndex: 0 }]);
  }

  private drawLine(lines: GShape[], points: LatLng[] | null, strokes: Record<string, unknown>[]): GShape[] {
    if (!points || points.length < 2) {
      lines.forEach((line) => line.setMap(null));
      return [];
    }
    const path = points.map(literal);
    if (lines.length === strokes.length) {
      lines.forEach((line, index) => line.setOptions({ ...strokes[index], path }));
      return lines;
    }
    lines.forEach((line) => line.setMap(null));
    return strokes.map(
      (stroke) => new this.view.maps.Polyline({ ...stroke, path, clickable: false, map: this.view.map })
    );
  }

  setZones(zones: ZoneCircle[]): void {
    this.zones.forEach((zone) => zone.setMap(null));
    this.zones = zones.map(
      (zone) =>
        new this.view.maps.Circle({
          center: literal(zone.center),
          radius: zone.radius,
          fillColor: zone.color,
          fillOpacity: 0.2,
          strokeWeight: 0,
          clickable: false,
          map: this.view.map,
        })
    );
  }

  /** Take everything off a map that is staying. */
  destroy(): void {
    this.removeCar();
    this.setDestination(null, null, "");
    this.setRoute(null, "");
    this.setTrail(null, "");
    this.setZones([]);
    this.trafficLayer?.setMap(null);
  }

  /** The map outlives a reconnect (fact 5), so there is nothing to forget. */
  abandon(): void {
    this.destroy();
  }
}
