/**
 * The visual editor: one `ha-form` over the whole config.
 *
 * It never writes a default into the dashboard, so an untouched option stays out
 * of the YAML and keeps following the card's default. It doesn't validate either:
 * `setConfig` on the card is the one place that decides what is valid.
 */

import { LitElement, css, html, nothing, type TemplateResult } from "lit";
import { property, state } from "lit/decorators.js";
import {
  EDITOR_TYPE,
  FOLLOWS,
  HUDS,
  HUD_FIELDS,
  HUD_POSITIONS,
  MARKER_STYLES,
  MODELS,
  ROOFS,
  UNITS,
  WHEN_PARKED,
} from "./config";
import type { HomeAssistant } from "./tesla-drive-tracker-card";

const LABELS: Record<string, string> = {
  entry_id: "Car",
  model: "Model",
  color: "Paint (auto, a paint name or a hex colour)",
  roof: "Roof",
  image: "Your own top-down picture",
  image_nose: "Which way the picture's nose points (degrees)",
  marker_style: "Marker",
  marker_size: "Marker size",
  follow: "Follow",
  recenter_after: "Recentre after touching the map (0 = never)",
  speed_zoom: "Zoom out with speed",
  height: "Map height",
  show_zones: "Show zones",
  show_route: "Show the route",
  route_color: "Route colour",
  show_trail: "Show the trail",
  trail_color: "Trail colour",
  trail_minutes: "Trail length in minutes (empty = the whole trip)",
  hud: "Info panel",
  hud_fields: "Info panel fields",
  hud_position: "Info panel position",
  units: "Units",
  when_parked: "When parked",
  smooth_motion: "Smooth motion between fixes",
  car: "Car",
  map: "Map",
  lines: "Lines",
  panel: "Info panel",
};

const pick = (options: readonly string[]) => ({ select: { mode: "dropdown", options: [...options] } });
const whole = (min: number, max: number, unit?: string) => ({
  number: { min, max, step: 1, mode: "box", unit_of_measurement: unit },
});

const group = (name: string, schema: unknown[]) => ({ type: "expandable", name, flatten: true, schema });

function schemaFor(cars: { entry_id: string; name: string }[]): unknown[] {
  return [
    ...(cars.length > 1
      ? [
          {
            name: "entry_id",
            selector: {
              select: {
                mode: "dropdown",
                options: cars.map((car) => ({ value: car.entry_id, label: car.name })),
              },
            },
          },
        ]
      : []),
    group("car", [
      { name: "model", selector: pick(MODELS) },
      { name: "color", selector: { text: {} } },
      { name: "roof", selector: pick(ROOFS) },
      { name: "marker_style", selector: pick(MARKER_STYLES) },
      { name: "marker_size", selector: whole(24, 160, "px") },
      { name: "image", selector: { text: {} } },
      { name: "image_nose", selector: whole(0, 359, "°") },
    ]),
    group("map", [
      { name: "follow", selector: pick(FOLLOWS) },
      { name: "recenter_after", selector: whole(0, 600, "s") },
      { name: "speed_zoom", selector: { boolean: {} } },
      { name: "height", selector: whole(120, 1200, "px") },
      { name: "show_zones", selector: { boolean: {} } },
      { name: "when_parked", selector: pick(WHEN_PARKED) },
      { name: "smooth_motion", selector: { boolean: {} } },
    ]),
    group("lines", [
      { name: "show_route", selector: { boolean: {} } },
      { name: "route_color", selector: { text: {} } },
      { name: "show_trail", selector: { boolean: {} } },
      { name: "trail_color", selector: { text: {} } },
      { name: "trail_minutes", selector: whole(1, 1440, "min") },
    ]),
    group("panel", [
      { name: "hud", selector: pick(HUDS) },
      { name: "hud_position", selector: pick(HUD_POSITIONS) },
      {
        name: "hud_fields",
        selector: { select: { multiple: true, mode: "list", options: [...HUD_FIELDS] } },
      },
      { name: "units", selector: pick(UNITS) },
    ]),
  ];
}

interface CardHelpers {
  createCardElement(config: Record<string, unknown>): Promise<unknown>;
}

export class TeslaDriveTrackerCardEditor extends LitElement {
  static styles = css`
    .hint {
      margin: 12px 4px 0;
      font-size: 0.8rem;
      color: var(--secondary-text-color);
    }
  `;

  @property({ attribute: false }) public hass?: HomeAssistant;

  @state() private _config?: Record<string, unknown>;
  @state() private _cars: { entry_id: string; name: string }[] = [];

  setConfig(config: Record<string, unknown>): void {
    this._config = config;
  }

  connectedCallback(): void {
    super.connectedCallback();
    void this._ensureForm();
    void this.hass?.connection
      .sendMessagePromise<{ entry_id: string; name: string }[]>({ type: "tesla_drive_tracker/cars" })
      .then((cars) => {
        this._cars = cars;
      });
  }

  /** `ha-form` is only loaded for an editor that uses it, so ask for one. */
  private async _ensureForm(): Promise<void> {
    if (customElements.get("ha-form")) return;
    const helpers = (await (window as unknown as { loadCardHelpers?: () => Promise<CardHelpers> }).loadCardHelpers?.()) as
      | CardHelpers
      | undefined;
    const card = (await helpers?.createCardElement({ type: "entities", entities: [] })) as
      | { constructor: { getConfigElement?: () => Promise<unknown> } }
      | undefined;
    await card?.constructor?.getConfigElement?.();
    this.requestUpdate();
  }

  private _label = (schema: { name: string }): string => LABELS[schema.name] ?? schema.name;

  private _changed = (event: CustomEvent): void => {
    const next: Record<string, unknown> = { ...this._config, ...(event.detail.value as Record<string, unknown>) };
    // A cleared option goes back to following the default.
    for (const [key, value] of Object.entries(next)) {
      if (value === undefined || value === "") delete next[key];
    }
    this.dispatchEvent(new CustomEvent("config-changed", { detail: { config: next }, bubbles: true, composed: true }));
  };

  protected render(): TemplateResult | typeof nothing {
    if (!this._config || !this.hass) return nothing;
    return html`
      <ha-form
        .hass=${this.hass}
        .data=${this._config}
        .schema=${schemaFor(this._cars)}
        .computeLabel=${this._label}
        @value-changed=${this._changed}
      ></ha-form>
      <p class="hint">An option left blank follows the default and isn't written to the dashboard.</p>
    `;
  }
}

if (!customElements.get(EDITOR_TYPE)) {
  customElements.define(EDITOR_TYPE, TeslaDriveTrackerCardEditor);
}
