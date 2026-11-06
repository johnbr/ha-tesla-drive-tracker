import { css } from "lit";

export const cardStyles = css`
  :host {
    display: block;
  }
  ha-card {
    overflow: hidden;
    position: relative;
  }
  .map-wrap {
    position: relative;
  }
  ha-map {
    display: block;
    height: 100%;
    width: 100%;
  }
  .hud {
    position: absolute;
    left: 8px;
    right: 8px;
    z-index: 2;
    display: flex;
    flex-wrap: wrap;
    align-items: baseline;
    gap: 2px 14px;
    padding: 8px 12px;
    border-radius: 12px;
    background: color-mix(in srgb, var(--card-background-color, #fff) 88%, transparent);
    color: var(--primary-text-color);
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
    pointer-events: none;
  }
  .hud.top {
    top: 8px;
  }
  .hud.bottom {
    bottom: 8px;
  }
  .destination {
    flex-basis: 100%;
    font-weight: 500;
    overflow: hidden;
    text-overflow: ellipsis;
    white-space: nowrap;
  }
  .field {
    font-size: 0.95rem;
    white-space: nowrap;
  }
  .field span {
    color: var(--secondary-text-color);
    font-size: 0.8rem;
    margin-left: 3px;
  }
  .hud.compact .field span {
    display: none;
  }
  .stale {
    position: absolute;
    top: 8px;
    left: 50%;
    transform: translateX(-50%);
    z-index: 3;
    padding: 4px 10px;
    border-radius: 12px;
    background: var(--warning-color, #ffa600);
    color: #000;
    font-size: 0.8rem;
    pointer-events: none;
    white-space: nowrap;
  }
  .recentre {
    position: absolute;
    top: 8px;
    right: 8px;
    z-index: 3;
    width: 40px;
    height: 40px;
    padding: 8px;
    border: 0;
    border-radius: 50%;
    background: var(--card-background-color, #fff);
    color: var(--primary-text-color);
    box-shadow: 0 1px 4px rgba(0, 0, 0, 0.3);
    cursor: pointer;
  }
  .recentre svg {
    width: 24px;
    height: 24px;
    fill: currentColor;
    display: block;
  }
  .message {
    padding: 16px;
    color: var(--secondary-text-color);
  }
  .message.error {
    color: var(--error-color);
  }
  .compact-line {
    padding: 12px 16px;
    color: var(--primary-text-color);
  }
`;

/** The marker lives in the map's own DOM, outside this card's shadow root. */
export const markerStyles = `
.tdt-car svg { width: 100%; height: 100%; display: block; overflow: visible; }
`;
