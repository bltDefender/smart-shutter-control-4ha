# Smart Shutter Control for Home Assistant

Automatische Rollladensteuerung abhängig vom Sonnenstand und der Außentemperatur –
voll konfigurierbar pro Fenster, mit visueller Lovelace-Karte.

---

## Funktionsweise

Die Integration berechnet für jedes konfigurierte Fenster den **Winkelabstand zwischen
Fenster-Ausrichtung und aktuellem Sonnenazimut**. In Kombination mit der Außentemperatur
werden die Rollladen automatisch in einen von drei Zuständen versetzt:

| Bedingung | Zustand |
|---|---|
| Winkelabstand < *Voll-schließen-Schwelle* & Temp ≥ Schwelle & Tagzeit | **Voll geschlossen** |
| Winkelabstand < *Halb-schließen-Schwelle* & Temp ≥ Schwelle & Tagzeit | **Halb geschlossen** |
| Sonnenuntergang erreicht **oder** Temp < Schwelle **oder** Sonne zeigt weg | **Voll geöffnet** |

Die **Tagzeit** endet beim konfigurierten Sonnenuntergang-Typ (bürgerlich / nautisch / astronomisch).

> **Beispiel:** Fenster nach Süden (180°), Schwelle 30° / 60°.  
> Sonnenazimut 175° → Winkelabstand 5° → voll geschlossen.  
> Sonnenazimut 220° → Winkelabstand 40° → halb geschlossen.  
> Sonnenazimut 280° → Winkelabstand 100° → geöffnet.

---

## Installation

### 1. Integration (custom_components)

Kopiere den Ordner `custom_components/smart_shutter/` in dein HA-Konfigurationsverzeichnis:

```
config/
└── custom_components/
    └── smart_shutter/    ← hier hin
```

### 2. Lovelace-Karte (www)

Kopiere `www/smart-shutter-card.js` in dein HA-`www`-Verzeichnis:

```
config/
└── www/
    └── smart-shutter-card.js    ← hier hin
```

Füge die Karte in **Einstellungen → Dashboards → Ressourcen** hinzu:

| URL | Typ |
|---|---|
| `/local/smart-shutter-card.js` | JavaScript-Modul |

### 3. HA neu starten

---

## Einrichtung

1. **Einstellungen → Geräte & Dienste → Integration hinzufügen → "Smart Shutter Control"**
2. Grundkonfiguration:
   - Breitengrad / Längengrad (wird aus HA-Konfiguration vorausgefüllt)
   - Temperatursensor(en) – bei mehreren wird der Mittelwert verwendet
   - Temperaturschwelle (Standard: 30 °C)
   - Sonnenuntergang-Typ
3. Nach dem Einrichten: **Konfigurieren** → Fenster verwalten:
   - **Fenster hinzufügen** – Name, Ausrichtung, Cover-Entität, Positionen, Winkelschwellen
   - **Fenster bearbeiten / entfernen** – jederzeit änderbar

---

## Lovelace-Karte

```yaml
type: custom:smart-shutter-card
entity: sensor.wohnzimmer_rollladen   # Name des SmartShutter-Sensor-Entities
title: Wohnzimmer Süd                  # optional
```

Die Karte zeigt:
- **SVG-Kompass** mit Fensterausrichtung (blauer Pfeil) und Sonnenposition (☀)
- **Farbige Zonen**: Rot = Voll-schließen-Bereich, Gelb = Halb-schließen-Bereich
- **Status-Pill**: aktueller Zustand mit Farbe (grün/orange/rot)
- **Infoleiste**: Sonnenazimut, -elevation, Winkelabstand, Temperatur
- **Hinweis**: wenn Automatik inaktiv (Nacht oder Temperatur zu niedrig)

---

## Entities

Pro Fenster wird eine Sensor-Entity erstellt:

| Attribut | Bedeutung |
|---|---|
| `state` | `open` / `half_closed` / `closed` |
| `window_orientation` | konfigurierte Ausrichtung in Grad |
| `sun_azimuth` | aktueller Sonnenazimut |
| `sun_elevation` | aktuelle Sonnenhöhe |
| `sun_angle_diff` | Winkelabstand Fenster ↔ Sonne |
| `temperature` | gemittelte Temperatur |
| `automation_active` | ob die Automatik gerade aktiv ist |

Zusätzlich gibt es eine globale Entity `sensor.smart_shutter_sonnenstand` mit
Sonnenposition und Temperaturstatus.

---

## Winkelschwellen – Empfehlungen

| Fenstertyp | Voll schließen | Halb schließen |
|---|---|---|
| Südseite (direkte Sonne) | 30° | 60° |
| Ost/West (schräge Sonne) | 20° | 45° |
| Nur Sonnenschutz gewünscht | 45° | 75° |

---

## Anforderungen

- Home Assistant ≥ 2023.3
- Built-in `sun` Integration muss aktiv sein
- Rollladen müssen als `cover`-Entität in HA vorhanden sein
