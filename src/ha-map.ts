/**
 * Borrowing Home Assistant's own `<ha-map>` instead of bundling a map library.
 *
 * `ha-map` is the element behind the built-in Map card, so the tiles, the
 * dark-mode handling and the pan/zoom behaviour are the ones the rest of the
 * dashboard already has -- at no cost to this bundle, and with no API key.
 *
 * Facts 1-4 were checked against the running frontend chunk (2026.8,
 * `frontend_latest/52451.*.js`), fact 5 against 2026.10.1 (`49854.*.js`), not
 * taken from documentation.
 *
 * 1. **It is lazily loaded.** On a dashboard with no Map card the tag is an
 *    inert unknown element. The only supported way to pull the chunk in is to
 *    ask the card helpers to build a `map` card and throw it away --
 *    `ensureHaMap()`.
 *
 * 2. **It takes no `hass`.** Since 2026.8 everything it needs (`_states`,
 *    `_config`, `_i18n`, `_formatters`, `_connection`) arrives over Lit context
 *    with `subscribe: true`. Context requests are composed DOM events, so they
 *    cross shadow boundaries and are answered at the app root -- which is why
 *    nothing is threaded through here, and why the element only works inside
 *    the Home Assistant app tree. A Lovelace card always is.
 *
 * 3. **It re-fits itself when `_loaded` flips, and that branch is not gated on
 *    `autoFit`:** `update()` runs `(changed.has("_loaded") || this.autoFit && …)
 *    && this.fitMap()`. With no entities, zones or `layers`, `fitMap()` takes an
 *    early return that centres on the *home* coordinates at zoom 14. So a fit
 *    performed before `_loaded` is true gets silently overwritten by that.
 *    `whenEngineReady()` therefore waits for `_loaded`, not just for an engine.
 *
 * 4. **`disconnectedCallback()` destroys the map** and clears `_loaded`.
 *    Everything drawn on it dies with it, so callers must key their own
 *    markers on the *engine instance* and rebuild when it changes, never on
 *    the element.
 *
 * 5. **Since 2026.10 the element is an engine wrapper.** It holds a pluggable
 *    `_engine` -- MapLibre (vector tiles) by default, Leaflet only when WebGL
 *    is unavailable or after the MapLibre engine dies -- and both engines
 *    implement the same drawing API, which is what the card draws through
 *    (see engine.ts). Facts 3 and 4 hold for both: `_loaded` flips once the
 *    engine is up, and `disconnectedCallback()` calls `_engine.destroy()`. A
 *    WebGL context loss also swaps the engine for a Leaflet one in place, so
 *    the card has to notice `_engine` changing even while it stays connected.
 *
 */

import type { MapEngine } from "./engine";

export interface HaMapElement extends HTMLElement {
  /** 2026.10+: the drawing engine. See fact 5. */
  _engine?: MapEngine;
  /** Its own "engine is up" flag. See fact 3. */
  _loaded?: boolean;
  autoFit?: boolean;
  zoom?: number;
  themeMode?: "auto" | "light" | "dark";
  /** `zoom` in the options is a MAX zoom, not a target. Default pad is 0.5. */
  fitBounds(latlngs: [number, number][], options?: { pad?: number; zoom?: number }): void;
  panTo(latlng: [number, number]): void;
  /** Centre and zoom, the zoom on Leaflet's scale whichever engine draws. */
  getView(): { center: [number, number]; zoom: number } | undefined;
  updateComplete: Promise<unknown>;
}

interface CardHelpers {
  createCardElement(config: Record<string, unknown>): Promise<unknown>;
}

declare global {
  interface Window {
    loadCardHelpers?: () => Promise<CardHelpers>;
  }
}

/** Ceiling on waiting for the lazy chunk. */
const LOAD_TIMEOUT_MS = 10_000;

/** Ceiling on waiting for that element to bring its engine up. */
const READY_TIMEOUT_MS = 5_000;
const READY_POLL_MS = 50;

/** Shared across every card instance: the chunk only needs importing once. */
let haMapPromise: Promise<boolean> | undefined;

export async function ensureHaMap(): Promise<boolean> {
  if (customElements.get("ha-map")) return true;

  haMapPromise ??= (async () => {
    try {
      const helpers = await window.loadCardHelpers?.();
      if (!helpers) return false;
      // Building a Map card is what imports the chunk defining `ha-map`; the
      // card itself is discarded. `show_all` is required because the card's own
      // setConfig rejects a config with neither entities nor
      // geo_location_sources, and that exception would be indistinguishable
      // from the chunk failing to load.
      await helpers.createCardElement({ type: "map", show_all: true });
    } catch {
      // Fall through: the import may have completed even if constructing the
      // throwaway card did not.
    }
    if (customElements.get("ha-map")) return true;
    // `whenDefined` never settles if the chunk genuinely failed, so it is
    // raced -- a map that never arrives must not leave the card on "Loading…".
    return Promise.race([
      customElements.whenDefined("ha-map").then(() => true),
      new Promise<boolean>((resolve) => setTimeout(() => resolve(false), LOAD_TIMEOUT_MS)),
    ]);
  })();

  return haMapPromise;
}

/**
 * Resolve with the engine once the element has one up *and* has flipped its
 * own `_loaded`.
 *
 * Waiting on the engine alone is not enough -- see fact 3. Returns undefined if
 * the map never comes up, which the caller must render as a failure rather than
 * an endless "Loading…".
 */
export async function whenEngineReady(el: HaMapElement): Promise<MapEngine | undefined> {
  const deadline = Date.now() + READY_TIMEOUT_MS;
  while (!(el._loaded && el._engine) && Date.now() < deadline) {
    await new Promise((resolve) => setTimeout(resolve, READY_POLL_MS));
  }
  return el._loaded ? el._engine : undefined;
}
