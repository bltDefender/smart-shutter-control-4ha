/**
 * Smart Shutter Card – Lovelace custom card
 *
 * Usage in Lovelace:
 *   type: custom:smart-shutter-card
 *   entity: sensor.wohnzimmer_rollladen   # SmartShutterWindowSensor entity
 *   title: Wohnzimmer                      # optional override
 *
 * Required entity attributes (all provided by the integration):
 *   window_orientation, sun_azimuth, sun_elevation, sun_angle_diff,
 *   temperature, temp_threshold, angle_fully_closed, angle_half_closed,
 *   is_daytime, temp_active, automation_active
 */

const CARD_VERSION = "1.0.0";

// ── Colour palette ────────────────────────────────────────────────────────

const C = {
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
  nightDot: "#37474f",
  inactive: "#9e9e9e",
  stateOpen: "#43a047",
  stateHalf: "#fb8c00",
  stateClosed: "#e53935",
};

// ── Math helpers ──────────────────────────────────────────────────────────

/**
 * Convert a compass bearing (0° = North, clockwise) to SVG (x, y).
 * SVG +x = East, +y = South, so we rotate the standard math angle by -90°.
 */
function compassToXY(bearing, r, cx, cy) {
  const rad = ((bearing - 90) * Math.PI) / 180;
  return [cx + r * Math.cos(rad), cy + r * Math.sin(rad)];
}

/**
 * Build an SVG arc-sector path that correctly handles wraparound bearings.
 * The sector sweeps clockwise from `fromBearing` to `toBearing` (compass).
 * Bearings are normalised internally so any numeric value is accepted.
 */
function sectorPath(fromBearing, toBearing, r, cx, cy) {
  // Normalise inputs to [0, 360) before computing the clockwise delta.
  fromBearing = ((fromBearing % 360) + 360) % 360;
  toBearing   = ((toBearing   % 360) + 360) % 360;
  const delta = ((toBearing - fromBearing) + 360) % 360;
  // Degenerate: zero-width sector
  if (delta === 0) return "";

  const [x1, y1] = compassToXY(fromBearing, r, cx, cy);
  const [x2, y2] = compassToXY(toBearing, r, cx, cy);
  const largeArc = delta > 180 ? 1 : 0;

  return `M ${cx},${cy} L ${x1},${y1} A ${r},${r} 0 ${largeArc},1 ${x2},${y2} Z`;
}

/** SVG sun icon centred at (cx, cy) with outer radius r. */
function sunSvg(cx, cy, r = 10) {
  const ri = r * 0.55;
  const ro = r * 1.55;
  const rays = 8;
  let d = "";
  for (let i = 0; i < rays; i++) {
    const a = (i * 360) / rays;
    const [xi, yi] = compassToXY(a, ri, cx, cy);
    const [xo, yo] = compassToXY(a, ro, cx, cy);
    d += `M${xi},${yi}L${xo},${yo}`;
  }
  return `<g>
    <path d="${d}" stroke="${C.sunRay}" stroke-width="1.5" stroke-linecap="round"/>
    <circle cx="${cx}" cy="${cy}" r="${r}" fill="${C.sunCore}" stroke="${C.sunBorder}" stroke-width="1.5"/>
  </g>`;
}

// ── Card element ──────────────────────────────────────────────────────────

class SmartShutterCard extends HTMLElement {
  constructor() {
    super();
    this.attachShadow({ mode: "open" });
  }

  setConfig(config) {
    if (!config.entity) throw new Error("smart-shutter-card: 'entity' is required");
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

    if (!stateObj) {
      this.shadowRoot.innerHTML = `<ha-card><div style="padding:16px">Entity <b>${entityId}</b> not found.</div></ha-card>`;
      return;
    }

    const title = this._config.title || stateObj.attributes.friendly_name || entityId;
    const attr = stateObj.attributes;
    const shutterState = stateObj.state; // "open" | "half_closed" | "closed"

    const orientation     = parseFloat(attr.window_orientation ?? 180);
    const sunAzimuth      = parseFloat(attr.sun_azimuth ?? 0);
    const sunElev         = parseFloat(attr.sun_elevation ?? -90);
    const angleDiffVal    = parseFloat(attr.sun_angle_diff ?? 0);
    const temp            = parseFloat(attr.temperature ?? 0);
    const tempThreshold   = parseFloat(attr.temp_threshold ?? 30);
    const angleFC         = parseFloat(attr.angle_fully_closed ?? 30);
    const angleHC         = parseFloat(attr.angle_half_closed ?? 60);
    const isDaytime       = attr.is_daytime === true;
    const tempActive      = attr.temp_active === true;
    const autoActive      = attr.automation_active === true;

    // ── SVG layout ────────────────────────────────────────────────────────
    const W = 240, H = 240, cx = W / 2, cy = H / 2, R = 95;
    const zoneR = R - 6;   // radius of zone sectors
    const sunR  = R + 8;   // sun icon orbit radius

    // Zone sectors: centred on window orientation, half-width = angle value.
    // We build from (orientation - angle) to (orientation + angle) clockwise.
    const hcFrom = ((orientation - angleHC) + 360) % 360;
    const hcTo   = (orientation + angleHC) % 360;
    const fcFrom = ((orientation - angleFC) + 360) % 360;
    const fcTo   = (orientation + angleFC) % 360;

    const halfArc = sectorPath(hcFrom, hcTo, zoneR, cx, cy);
    const fullArc = sectorPath(fcFrom, fcTo, zoneR, cx, cy);

    // Window direction pointer
    const [wx, wy] = compassToXY(orientation, R - 12, cx, cy);

    // Sun position
    const [sx, sy] = compassToXY(sunAzimuth, sunR, cx, cy);

    // ── Compass ticks ─────────────────────────────────────────────────────
    let ticks = "";
    for (let i = 0; i < 36; i++) {
      const isMajor = i % 9 === 0;
      const [x1, y1] = compassToXY(i * 10, R, cx, cy);
      const [x2, y2] = compassToXY(i * 10, R - (isMajor ? 8 : 4), cx, cy);
      ticks += `<line x1="${x1}" y1="${y1}" x2="${x2}" y2="${y2}"
        stroke="${C.tick}" stroke-width="${isMajor ? 1.5 : 0.8}"/>`;
    }

    // Cardinal labels at inner radius
    const labelR = R - 22;
    let cardinals = "";
    for (const [label, bearing] of [["N", 0], ["O", 90], ["S", 180], ["W", 270]]) {
      const [lx, ly] = compassToXY(bearing, labelR, cx, cy);
      cardinals += `<text x="${lx}" y="${ly + 4}" font-size="11" font-weight="600"
        fill="${C.compassText}" text-anchor="middle">${label}</text>`;
    }

    // ── State display ─────────────────────────────────────────────────────
    const stateColour =
      shutterState === "closed"      ? C.stateClosed :
      shutterState === "half_closed" ? C.stateHalf   : C.stateOpen;

    const stateLabel =
      shutterState === "closed"      ? "Geschlossen"     :
      shutterState === "half_closed" ? "Halb geschlossen" : "Geöffnet";

    const stateIcon =
      shutterState === "closed"      ? "▼▼" :
      shutterState === "half_closed" ? "▼"  : "▲";

    // ── Sun icon or night dot ─────────────────────────────────────────────
    const sunElement = isDaytime
      ? sunSvg(sx, sy, 9)
      : `<circle cx="${sx}" cy="${sy}" r="6" fill="${C.nightDot}" opacity="0.4"/>`;

    // ── Angle arc between window and sun (only when useful) ───────────────
    let arcBetween = "";
    if (isDaytime && angleDiffVal > 0 && angleDiffVal < 90) {
      // Determine which side the sun is on
      const cw = ((sunAzimuth - orientation) + 360) % 360;
      const arcFrom = cw <= 180 ? orientation : sunAzimuth;
      const arcTo   = cw <= 180 ? sunAzimuth  : orientation;
      arcBetween = `<path d="${sectorPath(arcFrom, arcTo, R - 28, cx, cy)}"
        fill="rgba(255,193,7,0.15)" stroke="rgba(255,193,7,0.5)"
        stroke-width="1" stroke-dasharray="3,2"/>`;
    }

    // ── Inactive note ─────────────────────────────────────────────────────
    const inactiveNote = autoActive ? "" : `
      <div style="font-size:11px;color:${C.inactive};margin-top:4px;text-align:center">
        ${!isDaytime
          ? "⏾ Nacht – Automatik inaktiv"
          : `🌡 ${temp.toFixed(1)}°C &lt; ${tempThreshold}°C – Automatik inaktiv`}
      </div>`;

    // ── Full SVG ──────────────────────────────────────────────────────────
    const svg = `
      <svg viewBox="0 0 ${W} ${H}" width="100%" style="max-width:${W}px;display:block;margin:0 auto">
        <circle cx="${cx}" cy="${cy}" r="${R}" fill="none"
          stroke="${C.compass}" stroke-width="1.5"/>
        <path d="${halfArc}" fill="${C.zoneHalf}" stroke="${C.zoneHalfStroke}" stroke-width="0.8"/>
        <path d="${fullArc}" fill="${C.zoneFull}" stroke="${C.zoneFullStroke}" stroke-width="0.8"/>
        ${ticks}
        ${cardinals}
        <line x1="${cx}" y1="${cy}" x2="${wx}" y2="${wy}"
          stroke="${C.windowLine}" stroke-width="2.5" stroke-linecap="round"/>
        <circle cx="${wx}" cy="${wy}" r="4" fill="${C.windowDot}"/>
        <circle cx="${cx}" cy="${cy}" r="3" fill="${C.windowLine}"/>
        ${arcBetween}
        ${sunElement}
        <text x="${cx}" y="${cy + 18}" text-anchor="middle" font-size="13"
          font-weight="600" fill="${stateColour}">${angleDiffVal.toFixed(1)}°</text>
      </svg>`;

    // ── HTML ──────────────────────────────────────────────────────────────
    this.shadowRoot.innerHTML = `
      <style>
        :host { display: block; }
        ha-card { padding: 16px; }
        .card-header { font-size: 16px; font-weight: 600; color: var(--primary-text-color); margin-bottom: 8px; }
        .content { display: flex; flex-direction: column; align-items: center; }
        .pill {
          display: inline-flex; align-items: center; gap: 6px;
          background: ${stateColour}22; border: 1.5px solid ${stateColour};
          border-radius: 20px; padding: 3px 12px; margin-top: 8px;
        }
        .pill-icon  { font-size: 13px; }
        .pill-label { font-size: 13px; font-weight: 600; color: ${stateColour}; }
        .info { display: flex; gap: 16px; font-size: 12px; color: #616161; margin-top: 8px; flex-wrap: wrap; justify-content: center; }
        .legend { display: flex; gap: 12px; margin-top: 8px; font-size: 11px; color: #757575; }
        .legend-item { display: flex; align-items: center; gap: 4px; }
        .legend-dot  { width: 10px; height: 10px; border-radius: 2px; }
      </style>
      <ha-card>
        <div class="card-header">${title}</div>
        <div class="content">
          ${svg}
          <div class="pill">
            <span class="pill-icon">${stateIcon}</span>
            <span class="pill-label">${stateLabel}</span>
          </div>
          <div class="info">
            <span>☀ Az. ${sunAzimuth.toFixed(0)}° / El. ${sunElev.toFixed(1)}°</span>
            <span>⟂ Δ ${angleDiffVal.toFixed(1)}°</span>
            <span>🌡 ${temp.toFixed(1)}°C</span>
          </div>
          ${inactiveNote}
          <div class="legend">
            <div class="legend-item">
              <div class="legend-dot" style="background:${C.zoneFull};border:1px solid ${C.zoneFullStroke}"></div>
              <span>Voll schließen ±${angleFC.toFixed(0)}°</span>
            </div>
            <div class="legend-item">
              <div class="legend-dot" style="background:${C.zoneHalf};border:1px solid ${C.zoneHalfStroke}"></div>
              <span>Halb schließen ±${angleHC.toFixed(0)}°</span>
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
