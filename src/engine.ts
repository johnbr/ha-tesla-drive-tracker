/**
 * `ha-map`'s engine-neutral drawing API, as of Home Assistant 2026.10.
 *
 * Since 2026.10 `ha-map` wraps a pluggable `_engine` -- MapLibre by default,
 * Leaflet when WebGL is missing -- and both engines implement the same small
 * surface: `addMarker` / `addCircle` / `addPath`, each returning a handle. This
 * file types the part of that surface the card uses, and papers over the one
 * place the two engines differ.
 *
 * Everything here was read off the running frontend (2026.10.1:
 * `frontend_latest/41645.*.js` is the MapLibre engine, `8200.*.js` the Leaflet
 * one, `49854.*.js` the `ha-map` element), not from documentation -- the API is
 * internal and undocumented, so re-check these facts first when a Home
 * Assistant release breaks the map.
 *
 * Facts that shape the code:
 *
 * 1. **`addMarker` takes an element WE own.** The engine sizes it and positions
 *    it; restyling is then a matter of rewriting its contents, which -- unlike
 *    Leaflet's `setIcon` -- keeps the node, so nothing blinks and no listener is
 *    lost.
 *
 * 2. **Only the MapLibre handle can move.** Its handle has `setLocation()`. The
 *    Leaflet handle has no such method; it exposes the raw `L.Marker` as
 *    `marker` instead (`ha-map`'s own draggable-marker shim moves one by
 *    removing and re-adding it). `moveMarker()` takes whichever is there. The
 *    Leaflet handle's `location` is a plain field set once, so it goes stale
 *    after a move -- read positions from our own bookkeeping, never from it.
 *
 * 3. **A path is one colour, a fixed 3 px wide, with per-segment opacity.**
 *    There is no weight, no dash and no `bringToFront`. On MapLibre each path
 *    is a pair of GeoJSON sources and layers inserted just below the basemap's
 *    first symbol layer, i.e. above every custom layer added before it -- so
 *    removing and re-adding a path is what raises it.
 *
 * 4. **MapLibre writes each marker's `transform` on every frame the map moves.**
 *    A CSS transition on that property would make the car trail behind the map
 *    during a pan, so motion is driven per animation frame instead (surface.ts).
 *
 * 6. **Stacking differs.** On MapLibre our element IS the positioned marker, so
 *    its `z-index` orders it among the others. On Leaflet it sits inside the
 *    engine's icon div and Leaflet orders markers by latitude plus a
 *    `zIndexOffset` (1000 for `raised`); `raiseMarker()` does both.
 *
 * 5. **Zoom levels are normalised.** MapLibre runs one level below Leaflet for
 *    the same scale; `ha-map`'s public `fitBounds` / `setView` / `getView`
 *    convert, so the card should only ever zoom through the element.
 */

export type EngineLatLng = [number, number];

export interface EngineMarkerOptions {
  /** Pixel box; the engine writes it onto the element. Centre-anchored. */
  size: [number, number];
  /** Pixel offset of the anchor from the top-left, if not the centre. */
  anchor?: [number, number];
  title?: string;
  /** false sets `pointer-events: none` on the element. Default true. */
  interactive?: boolean;
  focusable?: boolean;
  /** Draw above unraised markers. */
  raised?: boolean;
  /** false keeps `title` off the element's native tooltip. */
  nativeTitle?: boolean;
}

export interface EngineMarkerHandle {
  /** Where the marker was ADDED. Stale after a move on Leaflet; see fact 2. */
  readonly location: EngineLatLng;
  /** MapLibre only. */
  setLocation?(location: EngineLatLng): void;
  /** Leaflet only: the raw marker. */
  marker?: { setLatLng(location: EngineLatLng): unknown; setZIndexOffset?(offset: number): unknown };
  remove(): void;
}

export interface EnginePathSpec {
  color: string;
  segments: { points: EngineLatLng[]; opacity?: number }[];
  /** Dots along the path with a hover tooltip. Empty for a plain line. */
  markers: { location: EngineLatLng; opacity?: number; tooltipHtml: string }[];
}

export interface EnginePathHandle {
  update(spec: EnginePathSpec): void;
  remove(): void;
}

export interface EngineCircleOptions {
  /** Metres. */
  radius: number;
  color: string;
  outline?: boolean;
}

export interface MapEngine {
  addMarker(element: HTMLElement, location: EngineLatLng, options: EngineMarkerOptions): EngineMarkerHandle;
  addPath(spec: EnginePathSpec): EnginePathHandle;
  addCircle?(center: EngineLatLng, options: EngineCircleOptions): { remove(): void };
  /** Present only on the MapLibre engine. */
  _maplibre?: { getBearing?(): number };
  /** Present only on the Leaflet engine. */
  leafletMap?: { on(event: string, handler: () => void): unknown };
}

export type EngineKind = "maplibre" | "leaflet" | "unknown";

export function engineKind(engine: MapEngine): EngineKind {
  if (engine._maplibre) return "maplibre";
  if (engine.leafletMap) return "leaflet";
  return "unknown";
}

/** Move a marker on either engine. See fact 2. */
export function moveMarker(handle: EngineMarkerHandle, location: EngineLatLng): void {
  if (handle.setLocation) handle.setLocation(location);
  else handle.marker?.setLatLng(location);
}

/**
 * Put a marker above (or back among) the rest, on either engine. See fact 6.
 * `level` orders our own kinds on MapLibre: destination 0 < car 1.
 */
export function raiseMarker(handle: EngineMarkerHandle, element: HTMLElement, level: number, raised: boolean): void {
  element.style.zIndex = String(level);
  handle.marker?.setZIndexOffset?.(raised ? 1000 : 0);
}
