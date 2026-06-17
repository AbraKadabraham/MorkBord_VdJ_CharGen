# MorkBord VdJ CharGen

Automatischer Charakterbogen-Generator für **Vorzimmer des Jenseits** und **Mörk Borg** (Pen & Paper RPG).

Das Tool befüllt einen Charakterbogen (JPG-Vorlage) mit zufälligen Werten aus einer CSV-Tabelle und exportiert fertige A4-Seiten als PNG.

---

## Features

- **Zwei Systeme** per Dropdown umschaltbar: *Vorzimmer des Jenseits* und *Mörk Borg*
- **Vorschau** eines einzelnen Bogens direkt in der App
- **Seed-System** — reproduzierbare Ergebnisse; Seed kann manuell gesetzt oder automatisch gewürfelt werden
- **Pool-System** — kein Wert wiederholt sich, bevor alle Werte einmal gezogen wurden
- **Bögen pro Blatt** wählbar: 1, 2 oder 4 Bögen pro A4-Seite
- **Vollflächige Skalierung** — jeder Bogen füllt seine Zelle auf dem A4-Blatt komplett aus
- **Conditional Logic** in der Config (z. B. abhängige Felder)
- **Skip-Values** — bestimmte Würfelergebnisse werden übersprungen und die Zeile ausgelassen
- **Visueller Feld-Wizard** — Felder per Drag & Drop verschieben und skalieren
- **Schriftart pro Feld** — System-Fonts + eigene `.ttf`/`.otf` aus dem `fonts/`-Ordner
- **Attitude-Marker** (VdJ) — setzen, entfernen, Y-Position/Radius/Linienstärke anpassbar
- **Mörk Borg Stats** — Attributwerte, Trefferpunkte, Omen und Silber werden automatisch gewürfelt
- **Windows-EXE** via `build_exe.bat` (PyInstaller)

---

## Dateien

| Datei | Beschreibung |
|---|---|
| `charbogen_gui.py` | Haupt-App (GUI, Generierlogik, A4-Export) |
| `field_wizard.py` | Visueller Feld-Editor |
| `config.json` | Feldlayout für Vorzimmer des Jenseits |
| `config_mb.json` | Feldlayout für Mörk Borg |
| `RandomTables_VdJ.csv` | Zufallstabellen VdJ (semikolongetrennt) |
| `RandomTables_MB.csv` | Zufallstabellen Mörk Borg (semikolongetrennt) |
| `Charbogen_VdJ.jpg` | Bogenvorlage Vorzimmer des Jenseits |
| `Charbogen_MB.jpg` | Bogenvorlage Mörk Borg |
| `build_exe.bat` | Build-Skript für Windows-EXE (PyInstaller) |
| `requirements.txt` | Python-Abhängigkeiten |
| `fonts/` | Eigene Schriftarten (`.ttf`/`.otf`, optional) |

---

## Voraussetzungen

- Python 3.10+
- Abhängigkeiten installieren:

```bash
pip install -r requirements.txt
```

---

## Starten

```bash
python charbogen_gui.py
```

---

## Bedienung

### System wählen
Oben links im Dropdown zwischen *Vorzimmer des Jenseits* und *Mörk Borg* wechseln. Die App lädt automatisch die passende Config und Zufallstabelle.

### Vorschau
Die Vorschau zeigt immer einen zufällig erzeugten Bogen. Per „Aktualisieren" wird ein neuer Bogen mit neuem Seed generiert. Den Seed manuell eingeben und „Aktualisieren" klicken, um ein bestimmtes Ergebnis zu reproduzieren.

### Generieren
1. **Anzahl Bögen** eintragen (beliebige Zahl ≥ 1)
2. **Bögen pro Blatt** wählen: `1`, `2` oder `4`
3. **Generieren** klicken → Zielordner auswählen

Im Zielordner landen ausschließlich die fertigen A4-Seiten als PNG:

| Bögen pro Blatt | Format | Anordnung |
|---|---|---|
| 1 | A4 quer | Ein Bogen, füllt das Blatt vollständig |
| 2 | A4 hoch | Zwei Bögen übereinander |
| 4 | A4 quer | 2 × 2 Raster |

Ist die Anzahl der Bögen nicht durch 2 bzw. 4 teilbar, bleiben die übrigen Zellen auf der letzten Seite leer.

### Einstellungen
Über ⚙ Einstellungen lassen sich Template-Bild und CSV-Datei je System neu verknüpfen sowie der **Feld-Wizard** öffnen.

---

## Feld-Wizard

Der visuelle Editor erlaubt es, alle Felder direkt auf dem Bogen zu positionieren:

| Aktion | Bedienung |
|---|---|
| Feld auswählen | Klick auf Box im Canvas oder in der Feldliste links |
| Verschieben | Klick + Ziehen auf die farbige Box |
| Skalieren | An einem der 8 Handles an Ecken und Kanten ziehen |
| Neu aufziehen | Feld auswählen → „Neu aufziehen" → neue Box auf dem Canvas aufziehen |
| Schriftgröße | Spinbox im linken Panel |
| Ausrichtung | Dropdown: `left`, `center` |
| Schriftart | Dropdown mit allen verfügbaren System- und lokalen Fonts |

Änderungen werden direkt in `config.json` bzw. `config_mb.json` gespeichert.

### Attitude-Marker (nur VdJ)

| Aktion | Bedienung |
|---|---|
| Kreis setzen | Attitude-Modus aktiv → Linksklick auf den Canvas |
| Kreis entfernen | Rechtsklick auf einen Kreis |
| Y-Position / Radius / Linienstärke | Spinboxen im linken Panel |

---

## Config-Format

Die JSON-Configs steuern das Feldlayout. Wichtige Felder:

```jsonc
{
  "template_file": "Charbogen_VdJ.jpg",
  "csv_file": "RandomTables_VdJ.csv",
  "min_font_size": 14,
  "line_spacing": 6,
  "top_padding": 4,
  "a4_size": [3508, 2480],           // Querformat 300 DPI
  "a4_layout": { "margin": 90, "gap": 50 },
  "field_mapping": {
    "Feldname": "CSV-Spalte",         // einfache Zuordnung
    "Ausrüstung": ["Sp1", "Sp2"]     // mehrere Spalten → zusammengeführt
  },
  "field_layouts": {
    "Feldname": {
      "box": [x1, y1, x2, y2],
      "font_size": 22,
      "align": "left",               // left | center | right
      "font_file": "MeinFont.ttf",   // optional, aus fonts/
      "skip_values": ["nichts"],     // Werte die übersprungen werden
      "multi_column_separator": "\n"
    }
  },
  "conditional_logic": { ... },       // abhängige Felder
  "attitude_markers": { ... }         // nur VdJ
}
```

---

## Eigene Schriftarten

`.ttf`- oder `.otf`-Dateien einfach in den `fonts/`-Ordner legen. Sie erscheinen danach automatisch im Schriftart-Dropdown des Feld-Wizards und können pro Feld zugewiesen werden.

```
MorkBord_VdJ_CharGen/
└── fonts/
    ├── MeineSchriftart.ttf
    └── GothicDisplay.otf
```

---

## Windows-EXE bauen

```bat
build_exe.bat
```

Das Skript prüft alle Pflichtdateien, installiert Abhängigkeiten, baut die EXE mit PyInstaller und legt ein fertiges `release/`-Paket an:

```
release/
├── VdJ_CharGen.exe
├── config.json
├── config_mb.json
├── Charbogen_VdJ.jpg
├── Charbogen_MB.jpg
├── RandomTables_VdJ.csv
├── RandomTables_MB.csv
├── fonts/              (falls vorhanden)
├── Output/             (Zielordner, leer)
└── README.md
```

Die EXE kann direkt aus dem `release/`-Ordner gestartet werden. Alle Datendateien müssen sich im selben Ordner wie die EXE befinden.

---

## CSV-Format

Die CSV-Dateien müssen **semikolongetrennt** (`;`) und in **UTF-8** vorliegen. Die erste Zeile enthält die Spaltennamen. Leere Zeilen werden übersprungen. Alle Werte werden aus einem gemischten Pool gezogen — jeder Wert kommt erst wieder dran, wenn alle anderen einmal gezeigt wurden.

---

## Tech-Stack

- **Python 3.10+**
- **Tkinter** — GUI
- **Pillow** — Bildverarbeitung und PNG-Export
- **PyInstaller** — Windows-EXE-Build

---

## Lizenz

Dieses Tool ist ein inoffizielles Fan-Projekt und steht in keiner Verbindung zu Stockholm Kartell oder den Autoren von MÖRK BORG.  
Die Charakterbögen sowie die zugehörigen Inhalte liegen beim jeweiligen Rechteinhaber.

Der Code dieses Repositories steht unter der [MIT License](LICENSE).
