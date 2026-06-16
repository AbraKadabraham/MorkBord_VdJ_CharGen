# Vorzimmer des Jenseits — Charakterbogen-Generator

Ein Python-Tool zum automatischen Befüllen des **Vorzimmer des Jenseits**-Charakterbogens mit zufälligen Werten aus einer CSV-Tabelle. Vier fertig ausgefüllte Bögen werden auf einer druckfertigen A4-Seite (2×2-Raster, 300 DPI) als PNG gespeichert.

Das Tool richtet sich an Spielleiterinnen und Spielleiter, die schnell eine Gruppe von NSCs für **MÖRK BORG** und verwandte Systeme erzeugen wollen.

---

## Screenshots

> Charakterbogen-Vorlage: `Charbogen.jpg`

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
| `Charbogen.jpg` | Charakterbogen-Vorlage (Bilddatei) |
| `RandomTables.csv` | Tabelle mit Zufallswerten für alle Felder (Semikolon-getrennt, UTF-8) |
| `config.json` | Feldzuordnung und Textpositionen (bearbeitbar) |
| `requirements.txt` | Python-Abhängigkeiten |
| `build_exe.bat` | Windows-Skript zum Kompilieren einer EXE mit PyInstaller |
| `start_generator.bat` | Startet die EXE oder fällt auf Python-Skript zurück |

---

## Verwendung

### Als Python-Skript

```bash
python charbogen_gui.py
```

### Als Windows-EXE (selbst bauen)

1. `Charbogen.jpg`, `RandomTables.csv` und `config.json` in denselben Ordner legen wie `build_exe.bat`
2. `build_exe.bat` ausführen
3. Die fertige ausführbare Version liegt danach im Unterordner `release\`

```
release\
├── VdJ_CharGen.exe
├── Charbogen.jpg
├── RandomTables.csv
├── config.json
└── start_generator.bat
```

Das Build-Skript nutzt `python -m PyInstaller`, damit auch Benutzer-Installationen (AppData) korrekt erkannt werden.

---

## Bedienung der GUI

| Element | Funktion |
|---|---|
| **Anzahl Bögen** | Wie viele Charaktere generiert werden sollen (Standard: 4) |
| **Ausgabeordner** | Zielordner für die PNG-Dateien |
| **Seed** | Leer lassen für Zufall; manuellen Wert eintragen für reproduzierbare Ergebnisse |
| **Aktualisieren** | Neue Vorschau mit (neuem) Zufalls-Seed erzeugen |
| **Exportieren** | Alle Bögen plus A4-Seite als PNG speichern |

Bestehende Dateien werden **nicht überschrieben** — bei Namenskonflikt wird automatisch `_2`, `_3` usw. angehängt.

---

## CSV-Format

Die Datei `RandomTables.csv` muss **semikolongetrennt** und in **UTF-8** vorliegen. Die erste Zeile enthält die Spaltennamen. Relevante Spalten:

| Spalte | Zielfeld auf dem Bogen |
|---|---|
| `Name` | Name |
| `Schreckliche Eigenschaften` | Aussehen |
| `Art des Todes` | Art des Todes |
| `Offene Schuld` | Offene Schuld |
| `Kaputte Körper` | Eigenheiten |
| `Beunruhigende Geschichten` | Akte / Notizen |

Zusätzliche Spalten werden ignoriert. Leere Zeilen werden übersprungen.

---

## Feldzuordnung anpassen (`config.json`)

Die Datei `config.json` definiert, welche CSV-Spalte in welchen Bereich des Bogens geschrieben wird. Koordinaten sind Pixel-Koordinaten auf der Originalvorlage `Charbogen.jpg`.

```json
{
  "fields": {
    "Name": {
      "box": [55, 115, 370, 160],
      "font_size": 28
    },
    "Schreckliche Eigenschaften": {
      "box": [55, 205, 335, 400],
      "font_size": 22
    }
  }
}
```

- `box`: `[x1, y1, x2, y2]` — Textbereich in Pixel
- `font_size`: Maximale Startschriftgröße (wird automatisch verkleinert, wenn der Text nicht passt)

---

## Ausgabe

Pro Export-Durchlauf entstehen:

- `<basename>_001.png` … `<basename>_N.png` — Einzelbögen
- `<basename>_a4_page_1.png` … — A4-Seiten im 2×2-Raster (300 DPI, druckfertig)

Bereits vorhandene Dateien werden **nicht überschrieben**.

---

## Lizenz

Dieses Tool ist ein inoffizielles Fan-Projekt und steht in keiner Verbindung zu Stockholm Kartell oder den Autoren von MÖRK BORG.  
Der Charakterbogen „Vorzimmer des Jenseits" sowie die zugehörigen Inhalte liegen beim jeweiligen Rechteinhaber.

Der Code dieses Repositories steht unter der [MIT License](LICENSE).
