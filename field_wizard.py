"""field_wizard.py

Visueller Editor für alle Feldpositionen und Attitude-Marker.
Öffnet direkt die Gesamtübersicht (kein sequenzieller Wizard mehr).

Bedienung
---------
Felder (farbige Boxen):
  – Box verschieben : Klicken + Ziehen auf die Box
  – Größe ändern   : An einem der 8 Handles ziehen
  – Box neu ziehen : Feld links auswählen, dann "Neu aufziehen" klicken
                     und Box auf dem Bogen aufziehen

Attitude-Marker (grüne Kreise):
  – Neuen Kreis setzen : Linksklick auf freien Bereich im Attitude-Modus
  – Kreis löschen     : Rechtsklick auf einen Kreis
  – Y / Radius / Breite: Spinboxen im linken Panel

Linkes Panel:
  – Feld auswählen für Einzel-Aktionen
  – Schriftgröße, Ausrichtung und Schriftart pro Feld anpassen
  – Attitude-Einstellungen (Y, Radius, Linienstärke) — nur sichtbar wenn
    attitude_markers in der Config vorhanden ist

Speichern schreibt alle Werte in config.json.
"""

import json
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

from PIL import Image, ImageTk

_FIELD_COLORS = [
    '#e63946', '#2a9d8f', '#e9c46a', '#f4a261',
    '#457b9d', '#a8dadc', '#6a4c93', '#80b918',
]
_ATTITUDE_COLOR = '#00ff99'
_HANDLE_SIZE    = 7
_MIN_BOX        = 20
_CANVAS_MAX_W   = 1100
_CANVAS_MAX_H   = 780

# Bekannte Systemschriften (Windows / Linux / macOS)
_SYSTEM_FONTS = [
    ('Standard (automatisch)', ''),
    ('DejaVu Serif',      'DejaVuSerif.ttf'),
    ('DejaVu Sans',       'DejaVuSans.ttf'),
    ('Times New Roman',   'times.ttf'),
    ('Arial',             'arial.ttf'),
    ('Georgia',           'georgia.ttf'),
    ('Courier New',       'cour.ttf'),
    ('Verdana',           'verdana.ttf'),
    ('Trebuchet MS',      'trebuc.ttf'),
]

# Suchpfade für Systemschriften
_FONT_SEARCH_DIRS = [
    Path('C:/Windows/Fonts'),
    Path('/usr/share/fonts/truetype/dejavu'),
    Path('/usr/share/fonts/truetype/msttcorefonts'),
    Path('/usr/share/fonts/truetype'),
    Path('/Library/Fonts'),
    Path('/System/Library/Fonts'),
]


def _find_font_path(filename, app_dir):
    """Sucht eine .ttf-Datei: erst fonts/-Ordner, dann Systempfade."""
    if not filename:
        return None
    # 1) Lokaler fonts/-Ordner neben der App
    local = app_dir / 'fonts' / filename
    if local.exists():
        return local
    # 2) Systemweite Pfade
    for d in _FONT_SEARCH_DIRS:
        candidate = d / filename
        if candidate.exists():
            return candidate
    return None


def _collect_available_fonts(app_dir):
    """
    Gibt eine Liste von (Anzeigename, Dateiname) zurück.
    Enthält immer den Standard-Eintrag plus:
    - alle .ttf/.otf aus fonts/
    - bekannte Systemfonts die gefunden werden
    """
    entries = [('Standard (automatisch)', '')]
    seen_files = set()

    # Lokale fonts/ – alle .ttf/.otf
    fonts_dir = app_dir / 'fonts'
    if fonts_dir.is_dir():
        for f in sorted(fonts_dir.iterdir()):
            if f.suffix.lower() in ('.ttf', '.otf'):
                entries.append((f.stem, f.name))
                seen_files.add(f.name.lower())

    # Bekannte Systemschriften
    for name, filename in _SYSTEM_FONTS[1:]:  # [0] ist der Standard-Eintrag
        if filename.lower() in seen_files:
            continue
        if _find_font_path(filename, app_dir):
            entries.append((name, filename))
            seen_files.add(filename.lower())

    return entries


def _scale_box(box, scale):
    return [int(v * scale) for v in box]


def _unscale_box(box, scale):
    return [int(v / scale) for v in box]


class FieldWizard(tk.Toplevel):
    """Direkter Feldeditor – zeigt alle Felder + Attitude-Marker auf einmal."""

    def __init__(self, parent, config, config_path, reload_callback):
        super().__init__(parent)
        self.title('Felder & Marker anpassen')
        self.resizable(True, True)
        self.grab_set()

        self._config      = config
        self._config_path = Path(config_path)
        self._app_dir     = self._config_path.parent
        self._reload_cb   = reload_callback

        self._field_names = list(config['field_layouts'].keys())
        self._boxes = {
            n: list(config['field_layouts'][n]['box'])
            for n in self._field_names
        }
        self._font_sizes = {
            n: config['field_layouts'][n]['font_size']
            for n in self._field_names
        }
        self._aligns = {
            n: config['field_layouts'][n].get('align', 'left')
            for n in self._field_names
        }
        # Schriftart pro Feld: leerer String = automatisch (find_font-Logik)
        self._font_files = {
            n: config['field_layouts'][n].get('font_file', '')
            for n in self._field_names
        }

        # Verfügbare Fonts sammeln
        self._available_fonts = _collect_available_fonts(self._app_dir)
        self._font_display_names = [name for name, _ in self._available_fonts]
        self._font_file_names    = [fname for _, fname in self._available_fonts]

        # attitude_markers kann None sein (z.B. Mörk Borg hat keine)
        att = config.get('attitude_markers') or {}
        self._has_attitude = bool(att)
        self._att_x      = list(att.get('x_positions', []))
        self._att_y      = int(att.get('y', 50))
        self._att_radius = int(att.get('radius', 13))
        self._att_lw     = int(att.get('line_width', 3))

        self._mode           = 'fields'
        self._selected_field = self._field_names[0] if self._field_names else None
        self._draw_new_for   = None
        self._adj_active     = None

        # Bild laden – bei Fehler Dialog sauber schließen
        if not self._load_image():
            self.destroy()
            return

        self._build_ui()
        self._draw_all()

    # ------------------------------------------------------------------
    # Bild laden
    # ------------------------------------------------------------------

    def _load_image(self):
        """Lädt das Template-Bild. Gibt True zurück wenn erfolgreich, sonst False."""
        path = self._app_dir / self._config.get('template_file', '')
        try:
            self._orig = Image.open(path).convert('RGB')
        except FileNotFoundError:
            messagebox.showerror(
                'Template nicht gefunden',
                f'Das Template-Bild wurde nicht gefunden:\n{path}\n\n'
                'Bitte zuerst in den Einstellungen den korrekten Pfad hinterlegen.',
                parent=self,
            )
            return False
        except Exception as exc:
            messagebox.showerror(
                'Fehler beim Laden des Templates',
                f'Das Template-Bild konnte nicht geöffnet werden:\n{exc}',
                parent=self,
            )
            return False

        self._scale = min(
            _CANVAS_MAX_W / self._orig.width,
            _CANVAS_MAX_H / self._orig.height,
            1.0,
        )
        cw = int(self._orig.width  * self._scale)
        ch = int(self._orig.height * self._scale)
        self._tk_img    = ImageTk.PhotoImage(self._orig.resize((cw, ch), Image.LANCZOS))
        self._cw, self._ch = cw, ch
        return True

    # ------------------------------------------------------------------
    # UI aufbauen
    # ------------------------------------------------------------------

    def _build_ui(self):
        self.columnconfigure(1, weight=1)
        self.rowconfigure(0, weight=1)

        # ── Linkes Panel ─────────────────────────────────────────────────
        left = ttk.Frame(self, padding=(8, 8, 4, 8), width=240)
        left.grid(row=0, column=0, sticky='ns')
        left.grid_propagate(False)

        # Modus-Umschalter
        mode_frame = ttk.LabelFrame(left, text='Modus', padding=6)
        mode_frame.pack(fill='x', pady=(0, 8))
        self._mode_var = tk.StringVar(value='fields')
        ttk.Radiobutton(mode_frame, text='Felder', variable=self._mode_var,
                        value='fields',   command=self._on_mode_change).pack(anchor='w')
        if self._has_attitude:
            ttk.Radiobutton(mode_frame, text='Attitude-Marker', variable=self._mode_var,
                            value='attitude', command=self._on_mode_change).pack(anchor='w')

        # Feld-Liste
        field_frame = ttk.LabelFrame(left, text='Felder', padding=6)
        field_frame.pack(fill='both', expand=True, pady=(0, 8))
        self._field_listbox = tk.Listbox(field_frame, selectmode='single',
                                         height=10, activestyle='dotbox')
        self._field_listbox.pack(fill='both', expand=True)
        for i, name in enumerate(self._field_names):
            self._field_listbox.insert('end', name)
            self._field_listbox.itemconfigure(
                i, foreground=_FIELD_COLORS[i % len(_FIELD_COLORS)])
        if self._field_names:
            self._field_listbox.selection_set(0)
        self._field_listbox.bind('<<ListboxSelect>>', self._on_field_select)

        # Feld-Einstellungen
        fset_frame = ttk.LabelFrame(left, text='Feld-Einstellungen', padding=6)
        fset_frame.pack(fill='x', pady=(0, 8))

        # Schriftgröße
        ttk.Label(fset_frame, text='Schriftgröße:').grid(
            row=0, column=0, sticky='w', padx=(0, 4))
        self._fontsize_var = tk.IntVar(value=0)
        ttk.Spinbox(fset_frame, textvariable=self._fontsize_var,
                    from_=8, to=120, width=6,
                    command=self._on_fontsize_change).grid(row=0, column=1, sticky='w')
        self._fontsize_var.trace_add('write', lambda *_: self._on_fontsize_change())

        # Ausrichtung
        ttk.Label(fset_frame, text='Ausrichtung:').grid(
            row=1, column=0, sticky='w', pady=(6, 0))
        self._align_var = tk.StringVar(value='left')
        ttk.Combobox(fset_frame, textvariable=self._align_var,
                     values=['left', 'center', 'right'], width=8,
                     state='readonly').grid(row=1, column=1, sticky='w', pady=(6, 0))
        self._align_var.trace_add('write', lambda *_: self._on_align_change())

        # Schriftart
        ttk.Label(fset_frame, text='Schriftart:').grid(
            row=2, column=0, sticky='w', pady=(6, 0))
        self._font_var = tk.StringVar(value=self._font_display_names[0])
        self._font_combo = ttk.Combobox(
            fset_frame,
            textvariable=self._font_var,
            values=self._font_display_names,
            width=18,
            state='readonly',
        )
        self._font_combo.grid(row=2, column=0, columnspan=2, sticky='ew', pady=(6, 0))
        self._font_var.trace_add('write', lambda *_: self._on_font_change())

        # Neu aufziehen
        ttk.Button(fset_frame, text='Neu aufziehen',
                   command=self._start_redraw).grid(
            row=3, column=0, columnspan=2, sticky='ew', pady=(8, 0))
        ttk.Label(
            fset_frame,
            text='Feld auswählen, dann\n"Neu aufziehen" klicken\nund Box aufziehen.',
            foreground='gray', font=('TkDefaultFont', 8)
        ).grid(row=4, column=0, columnspan=2, sticky='w', pady=(4, 0))

        # Attitude-Einstellungen
        if self._has_attitude:
            att_frame = ttk.LabelFrame(left, text='Attitude-Marker', padding=6)
            att_frame.pack(fill='x', pady=(0, 8))

            self._att_y_var  = tk.IntVar(value=self._att_y)
            self._att_r_var  = tk.IntVar(value=self._att_radius)
            self._att_lw_var = tk.IntVar(value=self._att_lw)

            att_controls = [
                ('Y-Position:',    self._att_y_var,  0,    5000),
                ('Radius:',        self._att_r_var,  1,    200),
                ('Linienstärke:',  self._att_lw_var, 1,    20),
            ]
            for row_idx, (label, var, lo, hi) in enumerate(att_controls):
                ttk.Label(att_frame, text=label).grid(
                    row=row_idx, column=0, sticky='w', padx=(0, 4), pady=2)
                ttk.Spinbox(att_frame, textvariable=var, from_=lo, to=hi, width=7,
                            command=self._redraw_attitude).grid(
                    row=row_idx, column=1, sticky='w', pady=2)
                var.trace_add('write', lambda *_: self._redraw_attitude())

            self._att_count_lbl = ttk.Label(att_frame, text='', foreground='gray')
            self._att_count_lbl.grid(row=3, column=0, columnspan=2, sticky='w', pady=(4, 0))
            ttk.Label(
                att_frame,
                text='Im Attitude-Modus:\nLinksklick = Kreis setzen\nRechtsklick = Kreis entfernen',
                foreground='gray', font=('TkDefaultFont', 8)
            ).grid(row=4, column=0, columnspan=2, sticky='w', pady=(4, 0))
        else:
            self._att_y_var  = tk.IntVar(value=self._att_y)
            self._att_r_var  = tk.IntVar(value=self._att_radius)
            self._att_lw_var = tk.IntVar(value=self._att_lw)
            self._att_count_lbl = None
            info = ttk.LabelFrame(left, text='Attitude-Marker', padding=6)
            info.pack(fill='x', pady=(0, 8))
            ttk.Label(
                info,
                text='Dieses System verwendet\nkeine Attitude-Marker.',
                foreground='gray', font=('TkDefaultFont', 8)
            ).pack(anchor='w')

        # Speichern / Abbrechen
        btn_frame = ttk.Frame(left)
        btn_frame.pack(fill='x', side='bottom', pady=(4, 0))
        ttk.Button(btn_frame, text='💾 Speichern',
                   command=self._save).pack(fill='x', pady=(0, 4))
        ttk.Button(btn_frame, text='Abbrechen',
                   command=self.destroy).pack(fill='x')

        # ── Canvas ───────────────────────────────────────────────────────
        canvas_frame = ttk.Frame(self, padding=(4, 8, 8, 8))
        canvas_frame.grid(row=0, column=1, sticky='nsew')
        canvas_frame.rowconfigure(0, weight=1)
        canvas_frame.columnconfigure(0, weight=1)

        self._canvas = tk.Canvas(
            canvas_frame,
            width=self._cw, height=self._ch,
            bg='#1a1a1a',
            highlightthickness=1, highlightbackground='#555',
        )
        self._canvas.grid(row=0, column=0, sticky='nsew')

        self._status_var = tk.StringVar(value='Felder-Modus aktiv.')
        ttk.Label(canvas_frame, textvariable=self._status_var,
                  foreground='gray').grid(row=1, column=0, sticky='w', pady=(4, 0))

        self.geometry(f'{self._cw + 290}x{self._ch + 60}')
        self._sync_field_panel()
        self._bind_canvas()

    # ------------------------------------------------------------------
    # Modus-Handling
    # ------------------------------------------------------------------

    def _on_mode_change(self):
        self._mode = self._mode_var.get()
        self._draw_new_for = None
        self._bind_canvas()
        if self._mode == 'fields':
            self._status_var.set('Felder-Modus: Box ziehen oder Handle benutzen.')
        else:
            self._status_var.set(
                'Attitude-Modus: Linksklick = Kreis setzen, Rechtsklick = entfernen.')

    def _bind_canvas(self):
        c = self._canvas
        c.unbind('<ButtonPress-1>')
        c.unbind('<B1-Motion>')
        c.unbind('<ButtonRelease-1>')
        c.unbind('<ButtonPress-3>')
        c.config(cursor='crosshair' if self._mode == 'attitude' else 'arrow')
        if self._mode == 'fields':
            c.bind('<ButtonPress-1>',   self._field_press)
            c.bind('<B1-Motion>',        self._field_drag)
            c.bind('<ButtonRelease-1>', self._field_release)
        else:
            c.bind('<ButtonPress-1>',   self._att_left_click)
            c.bind('<ButtonPress-3>',   self._att_right_click)

    # ------------------------------------------------------------------
    # Feld-Panel synchronisieren
    # ------------------------------------------------------------------

    def _on_field_select(self, _event=None):
        sel = self._field_listbox.curselection()
        if sel:
            self._selected_field = self._field_names[sel[0]]
            self._sync_field_panel()

    def _sync_field_panel(self):
        if not self._selected_field:
            return
        self._fontsize_var.set(self._font_sizes[self._selected_field])
        self._align_var.set(self._aligns[self._selected_field])
        # Schriftart-Dropdown auf aktuellen Wert setzen
        current_file = self._font_files.get(self._selected_field, '')
        if current_file in self._font_file_names:
            idx = self._font_file_names.index(current_file)
            self._font_var.set(self._font_display_names[idx])
        else:
            self._font_var.set(self._font_display_names[0])  # Standard

    def _on_fontsize_change(self):
        if not self._selected_field:
            return
        try:
            self._font_sizes[self._selected_field] = int(self._fontsize_var.get())
        except (tk.TclError, ValueError):
            pass

    def _on_align_change(self):
        if not self._selected_field:
            return
        self._aligns[self._selected_field] = self._align_var.get()

    def _on_font_change(self):
        if not self._selected_field:
            return
        display_name = self._font_var.get()
        if display_name in self._font_display_names:
            idx = self._font_display_names.index(display_name)
            self._font_files[self._selected_field] = self._font_file_names[idx]

    # ------------------------------------------------------------------
    # Zeichnen
    # ------------------------------------------------------------------

    def _draw_all(self):
        c = self._canvas
        c.delete('all')
        c.create_image(0, 0, anchor='nw', image=self._tk_img)
        for name in self._field_names:
            self._draw_field_box(name)
        self._redraw_attitude()

    def _draw_field_box(self, name, redraw=False):
        c       = self._canvas
        tag_box = f'box_{name}'
        tag_lbl = f'lbl_{name}'
        tag_hdl = f'hdl_{name}'
        if redraw:
            c.delete(tag_box)
            c.delete(tag_lbl)
            c.delete(tag_hdl)

        b  = _scale_box(self._boxes[name], self._scale)
        x1, y1, x2, y2 = b
        is_sel = (name == self._selected_field)
        color  = _FIELD_COLORS[self._field_names.index(name) % len(_FIELD_COLORS)]
        lw     = 3 if is_sel else 1

        # Schriftart-Hinweis im Label anzeigen wenn gesetzt
        font_hint = self._font_files.get(name, '')
        label_text = name if not font_hint else f'{name} [{Path(font_hint).stem}]'

        c.create_rectangle(x1, y1, x2, y2, outline=color, width=lw, fill='',
                            tags=(tag_box, 'field_box'))
        c.create_text(x1 + 4, y1 + 4, anchor='nw', text=label_text, fill=color,
                      font=('TkDefaultFont', 9, 'bold' if is_sel else 'normal'),
                      tags=(tag_lbl, 'field_lbl'))

        if is_sel:
            hs = _HANDLE_SIZE
            mx, my = (x1 + x2) // 2, (y1 + y2) // 2
            for edge, (hx, hy) in {
                'nw': (x1, y1), 'n': (mx, y1), 'ne': (x2, y1),
                'e':  (x2, my),
                'se': (x2, y2), 's': (mx, y2), 'sw': (x1, y2),
                'w':  (x1, my),
            }.items():
                c.create_rectangle(
                    hx - hs, hy - hs, hx + hs, hy + hs,
                    fill=color, outline='white', width=1,
                    tags=(tag_hdl, f'hdl_{name}_{edge}', 'field_handle'))

    def _redraw_attitude(self):
        self._canvas.delete('attitude')
        if not self._has_attitude:
            return
        try:
            cy = int(self._att_y_var.get()  * self._scale)
            cr = max(1, int(self._att_r_var.get() * self._scale))
        except (tk.TclError, ValueError):
            return
        for i, img_x in enumerate(self._att_x):
            cx = int(img_x * self._scale)
            self._canvas.create_oval(
                cx - cr, cy - cr, cx + cr, cy + cr,
                outline=_ATTITUDE_COLOR, width=2, tags='attitude')
            self._canvas.create_text(
                cx, cy + cr + 10, text=str(i + 1),
                fill=_ATTITUDE_COLOR, font=('TkDefaultFont', 8), tags='attitude')
        if self._att_count_lbl:
            cnt = len(self._att_x)
            self._att_count_lbl.config(text=f"{cnt} Kreis{'e' if cnt != 1 else ''}")

    # ------------------------------------------------------------------
    # Feld-Interaktion: Verschieben + Handles
    # ------------------------------------------------------------------

    def _field_press(self, ev):
        if self._draw_new_for is not None:
            self._redraw_drag = {'x0': ev.x, 'y0': ev.y, 'rect': None}
            return

        items = self._canvas.find_overlapping(
            ev.x - _HANDLE_SIZE, ev.y - _HANDLE_SIZE,
            ev.x + _HANDLE_SIZE, ev.y + _HANDLE_SIZE)

        for item in reversed(items):
            for tag in self._canvas.gettags(item):
                if tag.startswith('hdl_') and tag.count('_') >= 2:
                    parts = tag[4:].rsplit('_', 1)
                    if len(parts) == 2 and parts[0] in self._field_names:
                        name, edge = parts
                        self._adj_active = {
                            'type': 'resize', 'name': name,
                            'edge': edge, 'lx': ev.x, 'ly': ev.y}
                        return

        for item in reversed(items):
            for tag in self._canvas.gettags(item):
                if tag.startswith('box_'):
                    name = tag[4:]
                    if name in self._field_names:
                        idx = self._field_names.index(name)
                        self._field_listbox.selection_clear(0, 'end')
                        self._field_listbox.selection_set(idx)
                        self._field_listbox.see(idx)
                        self._selected_field = name
                        self._sync_field_panel()
                        self._draw_all()
                        self._adj_active = {
                            'type': 'move', 'name': name,
                            'lx': ev.x, 'ly': ev.y}
                        return

    def _field_drag(self, ev):
        if self._draw_new_for is not None:
            d = self._redraw_drag
            if d.get('rect'):
                self._canvas.delete(d['rect'])
            d['rect'] = self._canvas.create_rectangle(
                d['x0'], d['y0'], ev.x, ev.y,
                outline='white', dash=(6, 4), width=2, tags='newbox')
            return

        if not self._adj_active:
            return
        a  = self._adj_active
        dx = ev.x - a['lx']
        dy = ev.y - a['ly']
        a['lx'], a['ly'] = ev.x, ev.y
        x1, y1, x2, y2  = _scale_box(self._boxes[a['name']], self._scale)

        if a['type'] == 'move':
            x1 += dx; y1 += dy; x2 += dx; y2 += dy
        else:
            edge = a['edge']
            if 'w' in edge: x1 += dx
            if 'e' in edge: x2 += dx
            if 'n' in edge: y1 += dy
            if 's' in edge: y2 += dy
            if x2 - x1 < _MIN_BOX: x2 = x1 + _MIN_BOX
            if y2 - y1 < _MIN_BOX: y2 = y1 + _MIN_BOX

        self._boxes[a['name']] = _unscale_box([x1, y1, x2, y2], self._scale)
        self._draw_field_box(a['name'], redraw=True)

    def _field_release(self, ev):
        if self._draw_new_for is not None:
            d  = self._redraw_drag
            self._canvas.delete('newbox')
            if d.get('rect'):
                self._canvas.delete(d['rect'])
            xs = sorted([d['x0'], ev.x])
            ys = sorted([d['y0'], ev.y])
            if (xs[1] - xs[0]) >= _MIN_BOX and (ys[1] - ys[0]) >= _MIN_BOX:
                self._boxes[self._draw_new_for] = _unscale_box(
                    [xs[0], ys[0], xs[1], ys[1]], self._scale)
            self._draw_new_for = None
            self._canvas.config(cursor='arrow')
            self._status_var.set('Box gespeichert.')
            self._draw_all()
            return
        self._adj_active = None

    def _start_redraw(self):
        if not self._selected_field:
            return
        self._mode_var.set('fields')
        self._mode = 'fields'
        self._bind_canvas()
        self._draw_new_for = self._selected_field
        self._redraw_drag  = {}
        self._canvas.config(cursor='crosshair')
        self._status_var.set(
            f'Neu aufziehen für \u201e{self._selected_field}\u201c – Box auf dem Bogen aufziehen.')

    # ------------------------------------------------------------------
    # Attitude-Interaktion
    # ------------------------------------------------------------------

    def _att_left_click(self, ev):
        self._att_x.append(int(ev.x / self._scale))
        self._att_x.sort()
        self._redraw_attitude()

    def _att_right_click(self, ev):
        if not self._att_x:
            return
        canvas_xs = [int(x * self._scale) for x in self._att_x]
        closest   = min(range(len(canvas_xs)),
                        key=lambda i: abs(canvas_xs[i] - ev.x))
        self._att_x.pop(closest)
        self._redraw_attitude()

    # ------------------------------------------------------------------
    # Speichern
    # ------------------------------------------------------------------

    def _save(self):
        for name in self._field_names:
            self._config['field_layouts'][name]['box']       = self._boxes[name]
            self._config['field_layouts'][name]['font_size'] = self._font_sizes[name]
            self._config['field_layouts'][name]['align']     = self._aligns[name]
            # font_file: leeren String nicht speichern (saubere Config)
            font_file = self._font_files.get(name, '')
            if font_file:
                self._config['field_layouts'][name]['font_file'] = font_file
            else:
                self._config['field_layouts'][name].pop('font_file', None)

        if self._has_attitude:
            try:
                self._config['attitude_markers']['x_positions'] = self._att_x
                self._config['attitude_markers']['y']           = int(self._att_y_var.get())
                self._config['attitude_markers']['radius']      = int(self._att_r_var.get())
                self._config['attitude_markers']['line_width']  = int(self._att_lw_var.get())
            except (tk.TclError, ValueError):
                pass

        try:
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
            messagebox.showinfo(
                'Gespeichert',
                'Alle Einstellungen wurden gespeichert.',
                parent=self)
        except Exception as exc:
            messagebox.showerror('Fehler beim Speichern', str(exc), parent=self)
            return

        self.destroy()
        if self._reload_cb:
            self._reload_cb()
