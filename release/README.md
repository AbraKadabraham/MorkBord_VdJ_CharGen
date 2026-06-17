# Vorzimmer des Jenseits — Charakterbogen-Generator

Ein Python-Tool zum automatischen Befüllen von Charakterbögen mit zufälligen Werten aus einer CSV-Tabelle. Vier fertig ausgefüllte Bögen werden auf einer druckfertigen A4-Seite (2×2-Raster, 300 DPI) als PNG gespeichert.

Das Tool richtet sich an Spielleiterinnen und Spielleiter, die schnell eine Gruppe von NSCs für **MÖRK BORG** und verwandte Systeme erzeugen wollen.

Aktuell unterstützte Systeme:
- **Vorzimmer des Jenseits** (`config.json` / `Charbogen_VdJ.jpg`)
- **Mörk Borg** (`config_mb.json` / `Charbogen_MB.jpg`)

---

## Screenshots

> Charakterbogen-Vorlagen: `Charbogen_VdJ.jpg`, `Charbogen_MB.jpg`

---

## Voraussetzungen

- **Python 3.10 oder neuer**
- **Pillow** (Bildverarbeitung)
- **Tkinter** (in Python-Standardinstallation enthalten)

Installation der Abhängigkeiten:

```bash
pip install -r requirements.txt
```

---

## Dateien

| Datei | Beschreibung |
|---|---|
| `charbogen_gui.py` | Hauptprogramm mit grafischer Benutzeroberfläche |
| `field_wizard.py` | Visueller Editor für Felder, Marker und Schriftarten |
| `Charbogen_VdJ.jpg` | Bogen-Vorlage: Vorzimmer des Jenseits |
| `Charbogen_MB.jpg` | Bogen-Vorlage: Mörk Borg |
| `RandomTables_VdJ.csv` | Zufallstabellen für Vorzimmer des Jenseits |
| `RandomTables_MB.csv` | Zufallstabellen für Mörk Borg |
| `config.json` | Feldkonfiguration für Vorzimmer des Jenseits |
| `config_mb.json` | Feldkonfiguration für Mörk Borg |
| `requirements.txt` | Python-Abhängigkeiten |
| `build_exe.bat` | Windows-Skript zum Kompilieren einer EXE mit PyInstaller |
| `start_generator.bat` | Startet die EXE oder fällt auf Python-Skript zurück |
| `install_requirements.bat` | Installiert alle Python-Abhängigkeiten per pip |

---

## Verwendung

### Als Python-Skript

```bash
python charbogen_gui.py
```

### Als Windows-EXE (selbst bauen)

1. `build_exe.bat` ausführen
2. Die fertige Version liegt danach im Unterordner `release\`

```
release\
├── VdJ_CharGen.exe
├── Charbogen_VdJ.jpg
├── Charbogen_MB.jpg
├── RandomTables_VdJ.csv
├── RandomTables_MB.csv
├── config.json
├── config_mb.json
└── start_generator.bat
```

Das Build-Skript nutzt `python -m PyInstaller`, damit auch Benutzer-Installationen (AppData) korrekt erkannt werden.

---

## Bedienung der GUI

| Element | Funktion |
|---|---|
| **System** | Umschalten zwischen „Vorzimmer des Jenseits" und „Mörk Borg" |
| **⚙ Einstellungen** | Dateipfade ändern und den Feld-Wizard öffnen |
| **Vorschau** | Zeigt einen zufällig befüllten Bogen in Echtzeit |
| **Seed** | Leer lassen für Zufall; manuellen Wert für reproduzierbare Ergebnisse eintragen |
| **Aktualisieren** | Neue Vorschau mit (neuem) Zufalls-Seed erzeugen |
| **Anzahl Bögen** | Wie viele Charaktere generiert werden sollen (Standard: 4) |
| **Generieren** | Zielordner auswählen und alle Bögen + A4-Seiten als PNG speichern |

Bestehende Dateien werden **nicht überschrieben** — bei Namenskonflikt wird automatisch `_2`, `_3` usw. angehängt.

---

## Felder visuell anpassen (Feld-Wizard)

Über **⚙ Einstellungen → 🗺 Felder anpassen** öffnet sich der visuelle Editor:

### Felder

| Aktion | Bedienung |
|---|---|
| Feld auswählen | Klick auf die Box im Canvas oder in der Feldliste links |
| Box verschieben | Klick + Ziehen auf die farbige Box |
| Größe ändern | An einem der 8 Handles (Anfasser) ziehen |
| Box neu aufziehen | Feld auswählen → „Neu aufziehen" → neue Box auf dem Bogen aufziehen |
| Schriftgröße | Spinbox im linken Panel (wird automatisch verkleinert wenn Text nicht passt) |
| Ausrichtung | Dropdown: `left` oder `center` |
| **Schriftart** | Dropdown: alle verfügbaren System- und lokalen Fonts |

### Schriftart pro Feld

Jedes Feld kann eine **eigene Schriftart** verwenden:

1. Feld in der Liste auswählen
2. Im Dropdown „Schriftart" die gewünschte Font wählen
3. „💾 Speichern" — der Wert wird in der `config.json` als `font_file` gespeichert

**Eigene Schriftarten einbinden:**  
`.ttf`- oder `.otf`-Dateien einfach in den Unterordner `fonts/` legen — sie erscheinen dann automatisch im Dropdown.

```
MorkBord_VdJ_CharGen/
└── fonts/
    ├── MeineSchriftart.ttf
    └── GothicDisplay.otf
```

Ist für ein Feld keine Schriftart gesetzt, wird automatisch eine verfügbare Systemschrift verwendet.

### Attitude-Marker (nur VdJ)

| Aktion | Bedienung |
|---|---|
| Neuen Kreis setzen | Attitude-Modus wählen → Linksklick auf den Canvas |
| Kreis entfernen | Rechtsklick auf einen Kreis |
| Y-Position / Radius / Linienstärke | Spinboxen im linken Panel |

---

## CSV-Format

Die CSV-Dateien müssen **semikolongetrennt** (`; `) und in **UTF-8** vorliegen. Die erste Zeile enthält die Spaltennamen.

### Vorzimmer des Jenseits (`RandomTables_VdJ.csv`)

| Spalte | Zielfeld auf dem Bogen |
|---|---|
| `Name` | Name |
| `Schreckliche Eigenschaften` | Aussehen |
| `Art des Todes` | Art des Todes |
| `Offene Schuld` | Offene Schuld |
| `Kaputte Körper` | Eigenheiten |
| `Beunruhigende Geschichten` | Akte / Notizen |

### Mörk Borg (`RandomTables_MB.csv`)

Die Spaltenzuordnung ist in `config_mb.json` unter `field_mapping` definiert und kann dort angepasst werden.

Zusätzliche Spalten werden ignoriert. Leere Zeilen werden übersprungen. Alle Werte werden aus einem gemischten Pool gezogen — jeder Wert kommt erst wieder dran, wenn alle anderen einmal gezeigt wurden.

---

## Feldzuordnung anpassen (`config.json`)

Die Config-Dateien definieren, welche CSV-Spalte in welchen Bereich des Bogens geschrieben wird.

```json
{
  "template_file": "Charbogen_VdJ.jpg",
  "csv_file": "RandomTables_VdJ.csv",
  "field_mapping": {
    "Name": "Name",
    "Aussehen": "Schreckliche Eigenschaften"
  },
  "field_layouts": {
    "Name": {
      "box": [55, 115, 370, 160],
      "font_size": 28,
      "align": "left",
      "font_file": "MeineSchriftart.ttf"
    }
  }
}
```

| Schlüssel | Beschreibung |
|---|---|
| `box` | `[x1, y1, x2, y2]` — Textbereich in Pixeln auf dem Original-Bild |
| `font_size` | Maximale Startschriftgröße (wird automatisch verkleinert wenn nötig) |
| `align` | `"left"` oder `"center"` |
| `font_file` | Dateiname der Schriftart (optional; leer = automatisch) |

---

## Ausgabe

Pro Export-Durchlauf entstehen:

- `charbogen_001.png` … `charbogen_N.png` — Einzelbögen
- `charbogen_a4_page_1.png` … — A4-Seiten im 2×2-Raster (300 DPI, druckfertig)

Bereits vorhandene Dateien werden **nicht überschrieben**.

---

## Lizenz

Dieses Tool ist ein inoffizielles Fan-Projekt und steht in keiner Verbindung zu Stockholm Kartell oder den Autoren von MÖRK BORG.  
Die Charakterbögen sowie die zugehörigen Inhalte liegen beim jeweiligen Rechteinhaber.

Der Code dieses Repositories steht unter der [MIT License](LICENSE).
