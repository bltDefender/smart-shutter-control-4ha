/**
 * Smart Shutter Card
 * Lovelace custom card for Smart Shutter Control integration.
 *
 * Usage in Lovelace:
 *   type: custom:smart-shutter-card
 *   entity: sensor.wohnzimmer_rollladen   # SmartShutterWindowSensor entity
 *   title: Wohnzimmer                      # optional
 *
 * The entity must expose these attributes (all provided by the integration):
 *   window_orientation, sun_azimuth, sun_elevation, sun_angle_diff,
 *   temperature, temp_threshold, angle_fully_closed, angle_half_closed,
 *   is_daytime, temp_active, automation_active
 */

const CARD_VERSION = "1.0.0";

// ── Colour palette ────────────────────────────────────────────────────────

const COLOURS = {
  compass: "#e0e0e0",
  compassText: "#9e9e9e",
  tick: "#bdbdbd",
  windowLine: "#1565c0",
  windowDot: "#1565c0",
  zoneHalf: "rgba(255,193,7,0.30)",
  zoneFull: "rgba(244,67,54,0.45)",
  zoneHalfStroke: "rgba(255,193,7,0.70)",
  zoneFullStroke: "rgba(244,67,54,0.85)",
  sunRay: "rgba(255,193,7,0.6)",
  sunCore: "#FDD835",
  sunBorder: "#F9A825",
  inactive: "#9e9e9e",
  stateOpen: "#43a047",
  stateHalf: "#fb8c00",
  stateClosed: "#e53935",
};

// ── Math helpers ──────────────────────────────────────────────────────────

/** Convert a compass bearing (0°=N, CW) to SVG coords on a circle. */
function compassToXY(bearing, radius, cx, cy) {
  const rad = ((bearing - 90) * Math.PI) / 180;
  return [cx + radius * Math.cos(rad), cy + radius * Math.sin(rad)];
}

/** Minimum angular distance 0–180 between two bearings. */
function angleDiff(a, b) {
  const d = Math.abs(a - b) % 360;
  return d > 180 ? 360 - d : d;
}

/** SVG arc path for a sector between two compass bearings. */
function arcPath(fromBearing, toBearing, r, cx, cy) {
  const [x1, y1] = compassToXY(fromBearing, r, cx, cy);
  const [x2, y2] = compassToXY(toBearing, r, cx, cy);
  const delta = ((toBearing - fromBearing + 360) % 360);
  const largeArc = delta > 180 ? 1 : 0;
  return `M ${cx},${cy} L ${x1},${y1} A ${r},${r} 0 ${largeArc},1 ${x2},${y2} Z`;
}

/** SVG sun icon centred at (cx, cy). */
function sunIcon(cx, cy, r = 10) {
  const rays = 8;
  const ri = r * 0.6;
  const ro = r * 1.5;
  let d = "";
  for (let i = 0; i < rays; i++) {
    const a = (i * 360) / rays;
    const [xi, yi] = compassToXY(a, ri, cx, cy);
    const [xo, yo] = compassToXY(a, ro, cx, cy);
    d += `M ${xi},${yi} L ${xo},${yo} `;
  }
  return `
    <g>
      <path d="${d}" stroke="${COLOURS.sunRay}" stroke-width="1.5" stroke-linecap="round"/>
      <circle cx="${cx}" cy="${cy}" r="${r}" fill="${COLOURS.sunCore}" stroke="${COLOURS.sunBorder}" stroke-width="1.5"/>
    </g>`;
}

// ── Card element ──────────────────────────────────────────────────────────

class SmartShutterCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    if (!config.entity) {
      throw new Error("smart-shutter-card: 'entity' is required");
    }
    this._config = config;
    this._render();
  }

  set hass(hass) {
    this._hass = hass;
    this._render();
  }

  _render() {
    if (!this._hass || !this._config) return;

    const entityId = this._config.entity;
    const stateObj = this._hass.states[entityId];
    const title = this._config.title || (stateObj ? stateObj.attributes.friendly_name : entityId);

    if (!stateObj) {
      this.shadowRoot.innerHTML = `<ha-card><div style="padding:16px">Entity ${entityId} not found.</div></ha-card>`;
      return;
    }

    const attr = stateObj.attributes;
    const shutterState = stateObj.state; // "open" | "half_closed" | "closed"
    const orientation = parseFloat(attr.window_orientation ?? 180);
    const sunAzimuth = parseFloat(attr.sun_azimuth ?? 0);
    const sunElev = parseFloat(attr.sun_elevation ?? -90);
    const angleDiffVal = parseFloat(attr.sun_angle_diff ?? 0);
    const temp = parseFloat(attr.temperature ?? 0);
    const tempThreshold = parseFloat(attr.temp_threshold ?? 30);
    const angleFullyClosed = parseFloat(attr.angle_fully_closed ?? 30);
    const angleHalfClosed = parseFloat(attr.angle_half_closed ?? 60);
    const isDaytime = attr.is_daytime === true;
    const tempActive = attr.temp_active === true;
    const automationActive = attr.automation_active === true;

    // SVG viewport
    const W = 240, H = 240, cx = W / 2, cy = H / 2, R = 95;

    // Zone arcs around window orientation
    const halfStart = (orientation - angleHalfClosed + 360) % 360;
    const halfEnd = (orientation + angleHalfClosed) % 360;
    const fullStart = (orientation - angleFullyClosed + 360) % 360;
    const fullEnd = (orientation + angleFullyClosed) % 360;

    const halfArc = arcPath(halfStart, halfEnd, R - 5, cx, cy);
    const fullArc = arcPath(fullStart, fullEnd, R - 5, cx, cy);

    // Window direction line
    const [wx, wy] = compassToXY(orientation, R - 10, cx, cy);

    // Sun position
    const sunR = R + 5;
    const [sx, sy] = compassToXY(sunAzimuth, sunR, cx, cy);

    // Compass ticks
    let ticks = "";
    for (let i = 0; i < 36; i++) {
      const len = i % 9 === 0 ? 8 : 4;
      const [x1, y1] = compassToXY(i * 10, R, cx, cy);
      const [x2, y2] = compassToXY(i * 10, R - len, cx, cy);
      ticks += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}" stroke="${COLOURS.tick}" stroke-width="${i % 9 === 0 ? 1.5 : 0.8}"/>`;
    }

    // Cardinal labels
    const cardinals = [
      { label: "N", bearing: 0, dx: -4, dy: 4 },
      { label: "O", bearing: 90, dx: -4, dy: 4 },
      { label: "S", bearing: 180, dx: -4, dy: 4 },
      { label: "W", bearing: 270, dx: -4, dy: 4 },
    ];
    const labelR = R - 22;
    let cardinalLabels = "";
    for (const c of cardinals) {
      const [lx, ly] = compassToXY(c.bearing, labelR, cx, cy);
      cardinalLabels += `<text x="${lx + c.dx}" y="${ly + c.dy}" font-size="11" font-weight="600" fill="${COLOURS.compassText}" text-anchor="middle">${c.label}</text>`;
    }

    // State colour and label
    const stateColour =
      shutterState === "closed"
        ? COLOURS.stateClosed
        : shutterState === "half_closed"
        ? COLOURS.stateHalf
        : COLOURS.stateOpen;

    const stateLabel =
      shutterState === "closed"
        ? "Geschlossen"
        : shutterState === "half_closed"
        ? "Halb geschlossen"
        : "Geöffnet";

    const stateIcon =
      shutterState === "closed"
        ? "▼▼"
        : shutterState === "half_closed"
        ? "▼"
        : "▲";

    // Only show sun icon if above horizon
    const sunIconSvg = isDaytime
      ? sunIcon(sx, sy, 9)
      : `<circle cx="${sx}" cy="${sy}" r="6" fill="#37474f" opacity="0.4"/>`;

    // Inactive overlay
    const inactiveNote = automationActive
      ? ""
      : `<div style="font-size:11px;color:${COLOURS.inactive};margin-top:2px">
          ${!isDaytime ? "⏾ Nacht – Automatik inaktiv" : !tempActive ? `🌡 ${temp.toFixed(1)}°C < ${tempThreshold}°C – Automatik inaktiv` : ""}
        </div>`;

    // Status pill
    const pill = `
      <div style="
        display:inline-flex;align-items:center;gap:6px;
        background:${stateColour}22;border:1.5px solid ${stateColour};
        border-radius:20px;padding:3px 12px;margin-top:6px;
      ">
        <span style="font-size:13px">${stateIcon}</span>
        <span style="font-size:13px;font-weight:600;color:${stateColour}">${stateLabel}</span>
      </div>`;

    // Info row
    const info = `
      <div style="display:flex;gap:16px;font-size:12px;color:#616161;margin-top:8px;flex-wrap:wrap;justify-content:center">
        <span>☀ Az. ${sunAzimuth.toFixed(0)}° / El. ${sunElev.toFixed(1)}°</span>
        <span>⟂ Δ ${angleDiffVal.toFixed(1)}°</span>
        <span>🌡 ${temp.toFixed(1)}°C</span>
      </div>`;

    // Full SVG
    const svg = `
      <svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px">
        <!-- Outer ring -->
        <circle cx="${cx}" cy="${cy}" r="${R}" fill="none" stroke="${COLOURS.compass}" stroke-width="1.5"/>
        <!-- Zone arcs -->
        <path d="${halfArc}" fill="${COLOURS.zoneHalf}" stroke="${COLOURS.zoneHalfStroke}" stroke-width="0.8"/>
        <path d="${fullArc}" fill="${COLOURS.zoneFull}" stroke="${COLOURS.zoneFullStroke}" stroke-width="0.8"/>
        <!-- Ticks + labels -->
        ${ticks}
        ${cardinalLabels}
        <!-- Window orientation line -->
        <line x1="${cx}" y1="${cy}" x2="${wx}" y2="${wy}"
              stroke="${COLOURS.windowLine}" stroke-width="2.5" stroke-linecap="round"/>
        <circle cx="${wx}" cy="${wy}" r="4" fill="${COLOURS.windowDot}"/>
        <!-- Centre dot -->
        <circle cx="${cx}" cy="${cy}" r="3" fill="${COLOURS.windowLine}"/>
        <!-- Sun -->
        ${sunIconSvg}
        <!-- Angle arc between window and sun -->
        ${isDaytime && angleDiffVal < 90
          ? `<path d="${arcPath(
              Math.min(orientation, sunAzimuth),
              Math.max(orientation, sunAzimuth),
              R - 28,
              cx,
              cy
            )}" fill="rgba(255,193,7,0.15)" stroke="rgba(255,193,7,0.5)" stroke-width="1" stroke-dasharray="3,2"/>`
          : ""}
        <!-- Angle text -->
        <text x="${cx}" y="${cy + 18}" text-anchor="middle" font-size="13" font-weight="600"
              fill="${stateColour}">${angleDiffVal.toFixed(1)}°</text>
      </svg>`;

    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { padding: 16px; }
        .card-header { font-size: 16px; font-weight: 600; color: var(--primary-text-color); margin-bottom: 8px; }
        .content { display: flex; flex-direction: column; align-items: center; }
        .legend { display: flex; gap: 12px; margin-top: 8px; font-size: 11px; color: #757575; }
        .legend-item { display: flex; align-items: center; gap: 4px; }
        .legend-dot { width: 10px; height: 10px; border-radius: 2px; }
      </style>
      <ha-card>
        <div class="card-header">${title}</div>
        <div class="content">
          ${svg}
          ${pill}
          ${info}
          ${inactiveNote}
          <div class="legend">
            <div class="legend-item">
              <div class="legend-dot" style="background:${COLOURS.zoneFull}; border:1px solid ${COLOURS.zoneFullStroke}"></div>
              <span>Voll schließen ±${angleFullyClosed.toFixed(0)}°</span>
            </div>
            <div class="legend-item">
              <div class="legend-dot" style="background:${COLOURS.zoneHalf}; border:1px solid ${COLOURS.zoneHalfStroke}"></div>
              <span>Halb schließen ±${angleHalfClosed.toFixed(0)}°</span>
            </div>
          </div>
        </div>
      </ha-card>`;
  }

  getCardSize() {
    return 4;
  }
}

customElements.define("smart-shutter-card", SmartShutterCard);

// Register card info for Lovelace picker
window.customCards = window.customCards || [];
window.customCards.push({
  type: "smart-shutter-card",
  name: "Smart Shutter Card",
  description: "Visualisiert Rollladen-Zustand und Sonnenstand als SVG-Kompass.",
  preview: true,
  documentationURL: "https://github.com/bltDefender/smart-shutter-control-4ha",
});

console.info(
  `%c SMART-SHUTTER-CARD %c v${CARD_VERSION} `,
  "background:#1565c0;color:#fff;font-weight:bold;padding:2px 4px;border-radius:3px 0 0 3px",
  "background:#e3f2fd;color:#1565c0;font-weight:bold;padding:2px 4px;border-radius:0 3px 3px 0"
);
