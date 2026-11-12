/**
 * Tesla Drive Tracker Card: a car's drive, live, on a map.
 *
 * Everything comes over `tesla_drive_tracker/subscribe`, already redacted, as one
 * snapshot and then small changes. `set hass` only stores the object: it fires on
 * every state change of every entity, and re-rendering on it would tear down the
 * map.
 */

import { LitElement, html, nothing, type TemplateResult } from "lit";
import { property, state } from "lit/decorators.js";
import { CARD_TYPE, EDITOR_TYPE, parseConfig, type CardConfig, type HudField } from "./config";
import { ensureHaMap, whenEngineReady, type HaMapElement } from "./ha-map";
import { viewAction, zoomForSpeed } from "./follow";
import {
  formatAge,
  formatDistance,
  formatMinutes,
  formatSpeed,
  formatTime,
  unitFor,
  type DistanceUnit,
} from "./format";
import { predict, routeAhead, turnTowards, type LatLng } from "./geo";
import { arrowSvg, carSvg, destinationSvg, dotSvg } from "./markers";
import { CarMotion } from "./motion";
import { outlineColor, paintColor, roofColor } from "./paint";
import { applyMessage, isStale, visibleTrail, type DriveState, type FeedMessage } from "./state";
import { cardStyles, markerStyles } from "./styles";
import { HaSurface, engineProblem, type MarkerArt, type ZoneCircle } from "./surface";

/** Read off this module's own URL, so the bundle has no version baked in. */
const VERSION = new URL(import.meta.url).searchParams.get("v") ?? "dev";
const DOCS = "https://github.com/johnbr/ha-tesla-drive-tracker";

/** How often to check that `ha-map` has not swapped its engine under us. */
const ENGINE_WATCH_MS = 2000;
/** How often the slower things on screen catch up: the age, and the lines. */
const REFRESH_MS = 3000;
/** A closed feed means the integration is reloading, so try again shortly. */
const RESUBSCRIBE_MS = 3000;
/** How long after a zoom starts to leave the marker alone, Leaflet only. */
const ZOOM_GUARD_MS = 2000;
const FIT_PAD = 0.2;
/** How often a moving car's view catches up with it, in seconds. */
const REFIT_SECONDS = 20;
const ZONE_COLOR = "#ff9800";

/** mdi:crosshairs-gps */
const RECENTRE_PATH =
  "M12,8A4,4 0 0,1 16,12A4,4 0 0,1 12,16A4,4 0 0,1 8,12A4,4 0 0,1 12,8M3.05,13H1V11H3.05C3.5,6.83 6.83,3.5 " +
  "11,3.05V1H13V3.05C17.17,3.5 20.5,6.83 20.95,11H23V13H20.95C20.5,17.17 17.17,20.5 13,20.95V23H11V20.95C6.83," +
  "20.5 3.5,17.17 3.05,13M12,5A7,7 0 0,0 5,12A7,7 0 0,0 12,19A7,7 0 0,0 19,12A7,7 0 0,0 12,5Z";

interface Connection {
  subscribeMessage(
    callback: (message: FeedMessage) => void,
    message: Record<string, unknown>
  ): Promise<() => Promise<void>>;
  sendMessagePromise<T>(message: Record<string, unknown>): Promise<T>;
}

export interface HomeAssistant {
  connection: Connection;
  config?: { unit_system?: { length?: string } };
  locale?: { language?: string; time_format?: string };
  language?: string;
  states: Record<string, { attributes: Record<string, unknown> } | undefined>;
}

interface CustomCard {
  type: string;
  name: string;
  description: string;
  preview?: boolean;
  documentationURL?: string;
}

declare global {
  interface Window {
    customCards?: CustomCard[];
  }
}

window.customCards = window.customCards ?? [];
if (!window.customCards.some((card) => card.type === CARD_TYPE)) {
  window.customCards.push({
    type: CARD_TYPE,
    name: "Tesla Drive Tracker",
    description: "A car's drive, live on a map, with its route, destination and arrival.",
    preview: false,
    documentationURL: DOCS,
  });
  // eslint-disable-next-line no-console
  console.info(
    `%c TESLA-DRIVE-TRACKER-CARD %c ${VERSION} `,
    "color:#fff;background:#1f2933;font-weight:700",
    "color:#1f2933;background:#90caf9;font-weight:700"
  );
}

/** Marker art goes inside the map, so its CSS has to reach the document. */
function ensureMarkerStyles(): void {
  const id = "tesla-drive-tracker-marker-styles";
  if (document.getElementById(id)) return;
  const style = document.createElement("style");
  style.id = id;
  style.textContent = markerStyles;
  document.head.append(style);
}

export class TeslaDriveTrackerCard extends LitElement {
  static styles = cardStyles;

  /** Set by Lovelace in edit mode, where a hidden card still has to show. */
  @property({ type: Boolean }) public preview = false;

  @state() private _config?: CardConfig;
  @state() private _mapAvailable: boolean | null = null;
  @state() private _problem?: string;
  @state() private _drive: DriveState | null = null;
  @state() private _following = true;

  /** Deliberately not reactive: assigning it must not schedule a render. */
  private _hass?: HomeAssistant;

  private _surface?: HaSurface;
  private _syncing = false;
  private _resync = false;
  private _unsubscribe?: () => Promise<void>;
  private _subscribing = false;
  private _resubscribe?: number;
  private _engineWatch?: number;
  private _refresh?: number;
  private _frame?: number;
  private _pausedUntil = 0;
  private _lastFixAt = 0;
  private _userAt: number | null = null;
  private _artKey = "";
  private _fitKey = "";
  private _fitAt = 0;
  private _lastRoute: LatLng[] | null = null;
  private _reducedMotion = window.matchMedia?.("(prefers-reduced-motion: reduce)");
  private _motion = new CarMotion(predict, turnTowards, () => this._smooth());

  set hass(hass: HomeAssistant) {
    const first = !this._hass;
    this._hass = hass;
    if (first) this._subscribe();
  }

  get hass(): HomeAssistant | undefined {
    return this._hass;
  }

  setConfig(config: unknown): void {
    const next = parseConfig(config);
    const carChanged = this._config?.entry_id !== next.entry_id;
    this._config = next;
    this._artKey = "";
    this._fitKey = "";
    this._surface?.destroy();
    this._surface = undefined;
    if (carChanged && this._hass) {
      this._unsubscribeFeed();
      this._subscribe();
    }
  }

  static async getConfigElement(): Promise<HTMLElement> {
    await import("./editor");
    return document.createElement(EDITOR_TYPE);
  }

  static getStubConfig(): Record<string, unknown> {
    return { type: `custom:${CARD_TYPE}` };
  }

  getCardSize(): number {
    return Math.ceil((this._config?.height ?? 400) / 50);
  }

  getGridOptions(): Record<string, unknown> {
    return { columns: 12, min_columns: 6, rows: "auto", min_rows: 6 };
  }

  connectedCallback(): void {
    super.connectedCallback();
    ensureMarkerStyles();
    if (this._mapAvailable === null) {
      void ensureHaMap().then((ok) => {
        this._mapAvailable = ok;
      });
    }
    // A WebGL context loss swaps MapLibre for Leaflet in place, taking every
    // marker with it while the card stays connected and nothing re-renders.
    this._engineWatch = window.setInterval(() => {
      const engine = this._mapEl()?._engine;
      if (this._surface && engine && engine !== this._surface.engine) void this._syncMap();
    }, ENGINE_WATCH_MS);
    this._refresh = window.setInterval(() => this._tick(), REFRESH_MS);
    if (this._hass) this._subscribe();
    void this._syncMap();
  }

  disconnectedCallback(): void {
    window.clearInterval(this._engineWatch);
    window.clearInterval(this._refresh);
    window.clearTimeout(this._resubscribe);
    this._stopFrames();
    this._unsubscribeFeed();
    // The markers die with the engine `ha-map` tears down.
    this._surface?.abandon();
    this._surface = undefined;
    this._artKey = "";
    this._fitKey = "";
    super.disconnectedCallback();
  }

  protected updated(): void {
    void this._syncMap();
  }

  private _smooth(): boolean {
    return (this._config?.smooth_motion ?? true) && !this._reducedMotion?.matches;
  }

  private _unsubscribeFeed(): void {
    void this._unsubscribe?.().catch(() => undefined);
    this._unsubscribe = undefined;
  }

  private async _entryId(): Promise<string | undefined> {
    if (this._config?.entry_id) return this._config.entry_id;
    const cars = await this._hass?.connection.sendMessagePromise<{ entry_id: string }[]>({
      type: "tesla_drive_tracker/cars",
    });
    return cars?.[0]?.entry_id;
  }

  private async _subscribe(): Promise<void> {
    if (this._unsubscribe || this._subscribing || !this._config || !this._hass) return;
    this._subscribing = true;
    try {
      const entryId = await this._entryId();
      if (!entryId) {
        this._problem = "No car found. Add one under Settings → Devices & services.";
        return;
      }
      this._unsubscribe = await this._hass.connection.subscribeMessage((message) => this._onMessage(message), {
        type: "tesla_drive_tracker/subscribe",
        entry_id: entryId,
      });
      this._problem = undefined;
    } catch (error) {
      this._problem = `Couldn't reach the car: ${(error as { message?: string }).message ?? error}`;
    } finally {
      this._subscribing = false;
    }
  }

  private _onMessage(message: FeedMessage): void {
    const now = Date.now();
    if (message.type === "closed") {
      this._unsubscribeFeed();
      this._resubscribe = window.setTimeout(() => void this._subscribe(), RESUBSCRIBE_MS);
      return;
    }
    const previous = this._drive;
    const next = applyMessage(previous, message, now / 1000);
    if (next === null) return;
    const moved =
      message.type === "snapshot" ||
      previous?.latitude !== next.latitude ||
      previous?.longitude !== next.longitude;
    this._drive = next;
    if (moved) {
      this._lastFixAt = message.type === "snapshot" && next.position_at ? next.position_at * 1000 : now;
      this._onFix(next, now);
    }
    this._ensureFrames();
  }

  private _onFix(drive: DriveState, now: number): void {
    if (drive.latitude === null || drive.longitude === null) return;
    this._motion.update(
      { position: [drive.latitude, drive.longitude], heading: drive.heading, speed: drive.speed },
      drive.route,
      now
    );
    this._syncView();
  }

  private _mapEl(): HaMapElement | null {
    return this.renderRoot?.querySelector<HaMapElement>("ha-map") ?? null;
  }

  private _showsMap(): boolean {
    const onDrive = this._drive?.driving || this._drive?.trip_started_at != null;
    return onDrive || this._config?.when_parked === "map" || this.preview;
  }

  private async _syncMap(): Promise<void> {
    if (this._mapAvailable !== true) return;
    if (this._syncing) {
      this._resync = true;
      return;
    }
    const el = this._mapEl();
    if (!el) return;

    this._syncing = true;
    try {
      const engine = await whenEngineReady(el);
      if (!engine) {
        if (el._loaded) this._problem = "This Home Assistant's map has no drawing API. The card needs 2026.10 or later.";
        return;
      }
      const problem = engineProblem(engine);
      if (problem) {
        this._problem = `${problem}, so this card can't draw on it.`;
        return;
      }
      if (this._surface?.engine !== engine) {
        this._surface?.abandon();
        this._surface = new HaSurface(engine);
        this._artKey = "";
        this._fitKey = "";
        engine.leafletMap?.on("zoomstart", () => this._pause());
        engine.leafletMap?.on("viewreset", () => this._pause());
        engine.leafletMap?.on("zoomend", () => (this._pausedUntil = 0));
        this._surface.setZones(this._zones());
        // `ha-map` fits itself when its `_loaded` flips. Waiting lets that happen
        // first, so the view set below is the last word.
        await el.updateComplete;
      }
      this._draw();
    } finally {
      this._syncing = false;
      if (this._resync) {
        this._resync = false;
        void this._syncMap();
      }
    }
  }

  private _pause(): void {
    this._pausedUntil = Date.now() + ZOOM_GUARD_MS;
  }

  private _zones(): ZoneCircle[] {
    if (!this._config?.show_zones || !this._hass) return [];
    const zones: ZoneCircle[] = [];
    for (const [id, entity] of Object.entries(this._hass.states)) {
      const { latitude, longitude, radius, passive } = entity?.attributes ?? {};
      if (id.startsWith("zone.") && !passive && typeof latitude === "number" && typeof longitude === "number") {
        zones.push({ center: [latitude, longitude], radius: Number(radius) || 100, color: ZONE_COLOR });
      }
    }
    return zones;
  }

  private _art(drive: DriveState, config: CardConfig): MarkerArt {
    const paint = paintColor(config.color, drive.paint);
    const look = { paint, roof: roofColor(config.roof, drive.roof, paint), outline: outlineColor(paint) };
    const size = config.marker_size;
    if (config.image) return { image: config.image, width: size, height: size, nose: config.image_nose };
    if (config.marker_style === "arrow") return { svg: arrowSvg(look), width: size * 0.6, height: size * 0.6, nose: 0 };
    if (config.marker_style === "dot") return { svg: dotSvg(look), width: size * 0.4, height: size * 0.4, nose: 0 };
    const model = config.model === "auto" ? drive.model : config.model;
    return { svg: carSvg(model, look), width: size / 2, height: size, nose: 0 };
  }

  /** Lines and the pin, which change far less often than the car. */
  private _draw(): void {
    const surface = this._surface;
    const drive = this._drive;
    const config = this._config;
    if (!surface || !drive || !config) return;

    const art = this._art(drive, config);
    const artKey = JSON.stringify(art);
    if (artKey !== this._artKey) {
      this._artKey = artKey;
      surface.setCarArt(art);
    }

    const position: LatLng | null =
      drive.latitude !== null && drive.longitude !== null ? [drive.latitude, drive.longitude] : null;
    if (position === null) surface.removeCar();

    const pin: LatLng | null =
      drive.destination_latitude !== null && drive.destination_longitude !== null
        ? [drive.destination_latitude, drive.destination_longitude]
        : null;
    surface.setDestination(pin, drive.destination, destinationSvg());

    const route = config.show_route && drive.route ? routeAhead(drive.route, position) : null;
    this._lastRoute = route;
    this._motion.setRoute(drive.route);
    surface.setRoute(route, config.route_color);
    surface.setTrail(
      config.show_trail ? visibleTrail(drive.trail, config.trail_minutes, Date.now() / 1000) : null,
      config.trail_color
    );
    this._drawCar(Date.now());
    this._syncView();
  }

  private _drawCar(now: number): void {
    if (!this._surface || now < this._pausedUntil) return;
    if (this._drive?.latitude == null) return;
    const drawn = this._motion.at(now);
    this._surface.moveCar(drawn.position, drawn.heading);
  }

  private _ensureFrames(): void {
    if (this._frame === undefined) this._frame = requestAnimationFrame(() => this._onFrame());
  }

  private _stopFrames(): void {
    if (this._frame !== undefined) cancelAnimationFrame(this._frame);
    this._frame = undefined;
  }

  private _onFrame(): void {
    this._frame = undefined;
    const now = Date.now();
    this._drawCar(now);
    // Stops itself once nothing moves, so a parked car costs no frames.
    if (this._motion.moving(now)) this._ensureFrames();
  }

  /** Move the view, unless the user has it or nothing calls for it. */
  private _syncView(): void {
    const el = this._mapEl();
    const drive = this._drive;
    const config = this._config;
    if (!el || !this._surface || !drive || !config || drive.latitude === null || drive.longitude === null) return;

    const now = Date.now() / 1000;
    const pin: LatLng[] =
      drive.destination_latitude !== null && drive.destination_longitude !== null
        ? [[drive.destination_latitude, drive.destination_longitude]]
        : [];
    const action = viewAction(config.follow, drive.driving, this._userAt, config.recenter_after, now, pin.length > 0);
    // With `off` there is nothing to return to, so no button either.
    const following = action !== "none" || config.follow === "off";
    if (following !== this._following) this._following = following;
    if (action !== "none") this._userAt = null;

    const position: LatLng = [drive.latitude, drive.longitude];
    if (action === "car") {
      this._fitKey = "";
      const zoom = config.speed_zoom ? zoomForSpeed(drive.speed) : undefined;
      const view = el.getView();
      if (zoom !== undefined && (!view || Math.abs(view.zoom - zoom) >= 1)) {
        el.fitBounds([position, position], { zoom, pad: 0 });
      } else {
        el.panTo(position);
      }
    } else if (action === "fit") {
      const points = [position, ...pin, ...(this._lastRoute ?? [])];
      // Fit when the picture changes or the car has moved on, not on every fix.
      const key = JSON.stringify([pin, points.length > 2, this._drive?.trip_started_at]);
      if (key !== this._fitKey || (drive.driving && now - this._fitAt >= REFIT_SECONDS)) {
        this._fitKey = key;
        this._fitAt = now;
        // Close to the pin the fit would otherwise zoom right in.
        const closest = drive.driving && config.speed_zoom ? { zoom: zoomForSpeed(drive.speed) } : {};
        el.fitBounds(points, points.length > 1 ? { pad: FIT_PAD, ...closest } : { zoom: 16, pad: 0 });
      }
    }
  }

  private _tick(): void {
    if (this._drive?.driving) {
      this.requestUpdate();
    }
    if (this._userAt !== null) this._syncView();
  }

  private _onUserMove = (): void => {
    if (this._config?.follow === "off") return;
    this._userAt = Date.now() / 1000;
    this._following = false;
  };

  private _onRecentre = (): void => {
    this._userAt = null;
    this._fitKey = "";
    this._following = true;
    this._syncView();
  };

  private _unit(): DistanceUnit {
    return unitFor(this._config?.units ?? "auto", this._hass?.config?.unit_system?.length);
  }

  private _field(field: HudField, drive: DriveState): TemplateResult | typeof nothing {
    const unit = this._unit();
    const item = (value: string, label: string): TemplateResult =>
      html`<div class="field">${value}<span>${label}</span></div>`;
    switch (field) {
      case "eta": {
        if (drive.arrival_at === null) return nothing;
        const format = this._hass?.locale?.time_format;
        const hour12 = format === "12" ? true : format === "24" ? false : undefined;
        const locale = this._hass?.locale?.language ?? this._hass?.language ?? "en";
        return item(formatTime(drive.arrival_at, locale, hour12), "ETA");
      }
      case "minutes":
        return drive.minutes === null ? nothing : item(formatMinutes(drive.minutes), "left");
      case "distance":
        return drive.distance === null ? nothing : item(formatDistance(drive.distance, unit), "left");
      case "speed":
        return drive.speed === null || !drive.driving ? nothing : item(formatSpeed(drive.speed, unit), "");
      case "battery":
        return drive.battery === null ? nothing : item(`${Math.round(drive.battery)}%`, "now");
      case "arrival_battery":
        return drive.arrival_battery === null ? nothing : item(`${Math.round(drive.arrival_battery)}%`, "on arrival");
      case "traffic_delay":
        return !drive.traffic_delay ? nothing : item(`+${formatMinutes(Math.round(drive.traffic_delay))}`, "traffic");
      default:
        return nothing;
    }
  }

  private _renderHud(drive: DriveState, config: CardConfig): TemplateResult | typeof nothing {
    if (config.hud === "off") return nothing;
    const fields = config.hud === "compact" ? config.hud_fields.slice(0, 4) : config.hud_fields;
    const items = fields.filter((field) => field !== "destination").map((field) => this._field(field, drive));
    const title = fields.includes("destination") && drive.destination ? drive.destination : undefined;
    if (!title && items.every((item) => item === nothing)) return nothing;
    // Lit escapes this text, so a destination name can't become markup.
    return html`<div class="hud ${config.hud_position} ${config.hud}">
      ${title ? html`<div class="destination">${title}</div>` : nothing}${items}
    </div>`;
  }

  private _renderStale(drive: DriveState): TemplateResult | typeof nothing {
    const now = Date.now() / 1000;
    if (!isStale(drive, this._lastFixAt / 1000, now)) return nothing;
    return html`<div class="stale">Last fix ${formatAge(now - this._lastFixAt / 1000)} ago</div>`;
  }

  protected render(): TemplateResult | typeof nothing {
    const config = this._config;
    if (!config) return nothing;
    if (this._problem) return html`<ha-card><div class="message error">${this._problem}</div></ha-card>`;
    if (this._mapAvailable === false) {
      return html`<ha-card><div class="message error">The map could not be loaded.</div></ha-card>`;
    }
    const drive = this._drive;
    if (!drive || this._mapAvailable === null) return html`<ha-card><div class="message">Loading…</div></ha-card>`;

    if (!this._showsMap()) {
      if (config.when_parked === "hide") return nothing;
      const battery = drive.battery === null ? "" : ` · ${Math.round(drive.battery)}%`;
      return html`<ha-card><div class="compact-line">${drive.state}${battery}</div></ha-card>`;
    }
    const hud = this._renderHud(drive, config);
    const outside = config.hud_position === "above" || config.hud_position === "below";
    return html`<ha-card>
      ${outside && config.hud_position === "above" ? hud : nothing}
      <div
        class="map-wrap"
        style="height:${config.height}px"
        @pointerdown=${this._onUserMove}
        @wheel=${this._onUserMove}
      >
        <ha-map .autoFit=${false} .themeMode=${"auto"}></ha-map>
        ${outside ? nothing : hud} ${this._renderStale(drive)}
        ${this._following
          ? nothing
          : html`<button class="recentre" title="Recentre" @click=${this._onRecentre}>
              <svg viewBox="0 0 24 24" aria-hidden="true"><path d=${RECENTRE_PATH}></path></svg>
            </button>`}
      </div>
      ${outside && config.hud_position === "below" ? hud : nothing}
    </ha-card>`;
  }
}

if (!customElements.get(CARD_TYPE)) {
  customElements.define(CARD_TYPE, TeslaDriveTrackerCard);
}
