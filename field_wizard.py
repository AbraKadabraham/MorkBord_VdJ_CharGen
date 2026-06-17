"""field_wizard.py

Mehrstufiger Wizard zum visuellen Festlegen der Feldkoordinaten
für den Charakterbogen.  Wird aus charbogen_gui.py heraus aufgerufen.

Ablauf
------
1. Dateipfade: Template-Bild und CSV können neu ausgewählt werden.
2. Für jedes Feld in config['field_layouts'] wird ein Schritt angezeigt,
   in dem der Benutzer auf dem Bogen-Canvas eine Box aufziehen kann.
3. Attitude-Marker-Schritt: Kreispositionen per Klick setzen, Y und Radius
   können danach angepasst werden.
4. Im letzten Schritt werden alle Boxen gleichzeitig dargestellt;
   einzelne Boxen lassen sich verschieben und in der Größe anpassen.
5. Auf Klick auf „Speichern“ werden die neuen Koordinaten in config.json
   geschrieben und die übergebene reload_callback-Funktion aufgerufen.
"""

import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog
from pathlib import Path

from PIL import Image, ImageTk

# Farben für die einzelnen Felder (zyklisch)
_FIELD_COLORS = [
    "#e63946", "#2a9d8f", "#e9c46a", "#f4a261",
    "#457b9d", "#a8dadc", "#6a4c93", "#80b918",
]

_ATTITUDE_COLOR = "#00ff99"
_HANDLE_SIZE = 8          # Pixel-Radius der Resize-Handles
_MIN_BOX = 20             # Mindestgröße einer Box in Canvas-Pixeln
_CANVAS_MAX_W = 1200
_CANVAS_MAX_H = 800


def _scale_box(box, scale):
    """Skaliert eine [x1,y1,x2,y2]-Box vom Bild- in den Canvas-Raum."""
    return [int(v * scale) for v in box]


def _unscale_box(box, scale):
    """Skaliert eine Box vom Canvas- zurück in den Bild-Raum."""
    return [int(v / scale) for v in box]


class FieldWizard(tk.Toplevel):
    """Haupt-Wizard-Fenster."""

    # Schritte: 0 = Dateipfade, 1..n = Felder, n+1 = Attitude, n+2 = Adjust
    _STEP_FILES = 0
    _STEP_ADJUST_OFFSET = 2  # nach allen Feld-Schritten

    def __init__(self, parent, config, config_path, reload_callback):
        super().__init__(parent)
        self.title("Felder anpassen – Wizard")
        self.resizable(True, True)
        self.grab_set()  # modal

        self.config_data = config
        self.config_path = Path(config_path)
        self.reload_callback = reload_callback
        self._app_dir = self.config_path.parent

        # Feld-Namen und aktuelle Boxen aus config laden
        self.field_names = list(config["field_layouts"].keys())
        self.boxes = {
            name: list(config["field_layouts"][name]["box"])
            for name in self.field_names
        }
        self.font_sizes = {
            name: config["field_layouts"][name]["font_size"]
            for name in self.field_names
        }
        self.aligns = {
            name: config["field_layouts"][name].get("align", "left")
            for name in self.field_names
        }

        # Attitude-Marker-Daten
        att = config["attitude_markers"]
        self._att_x = list(att["x_positions"])
        self._att_y = int(att["y"])
        self._att_radius = int(att["radius"])
        self._att_line_width = int(att.get("line_width", 3))

        # Dateipfade
        self._template_rel = config["template_file"]
        self._csv_rel = config["csv_file"]

        # Bild laden
        self._load_template_image()

        # Schritt-Aufbau:
        # 0            = Dateipfade
        # 1 .. n       = Felder (n = len(field_names))
        # n+1          = Attitude-Marker
        # n+2          = Adjust (alle Felder + Attitude)
        self._n_fields = len(self.field_names)
        self._step_attitude = self._n_fields + 1
        self._step_adjust   = self._n_fields + 2
        self._total_steps   = self._n_fields + 3  # 0..n+2

        self._step = 0
        self._build_ui()
        self._show_step()

    # ------------------------------------------------------------------
    # Bild laden / neu laden
    # ------------------------------------------------------------------

    def _load_template_image(self):
        template_path = self._app_dir / self._template_rel
        self._orig_img = Image.open(template_path).convert("RGB")
        self._scale = min(
            _CANVAS_MAX_W / self._orig_img.width,
            _CANVAS_MAX_H / self._orig_img.height,
            1.0,
        )
        cw = int(self._orig_img.width  * self._scale)
        ch = int(self._orig_img.height * self._scale)
        self._canvas_img = self._orig_img.resize((cw, ch), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(self._canvas_img)
        self._cw = cw
        self._ch = ch

    # ------------------------------------------------------------------
    # UI-Aufbau
    # ------------------------------------------------------------------

    def _build_ui(self):
        cw, ch = self._cw, self._ch
        self.columnconfigure(0, weight=1)
        self.rowconfigure(2, weight=1)

        # Kopfzeile
        header = ttk.Frame(self, padding=(12, 8))
        header.grid(row=0, column=0, sticky="ew")
        self._title_var = tk.StringVar()
        ttk.Label(header, textvariable=self._title_var,
                  font=("TkDefaultFont", 12, "bold")).pack(side="left")
        self._step_var = tk.StringVar()
        ttk.Label(header, textvariable=self._step_var).pack(side="right")

        # Instruktionen
        inst_frame = ttk.Frame(self, padding=(12, 0))
        inst_frame.grid(row=1, column=0, sticky="ew")
        self._inst_var = tk.StringVar()
        ttk.Label(inst_frame, textvariable=self._inst_var,
                  wraplength=900, justify="left").pack(fill="x")

        # Haupt-Bereich (Canvas + Datei-Frame werden gestapelt, nur eines sichtbar)
        self._main_frame = ttk.Frame(self, padding=(12, 6))
        self._main_frame.grid(row=2, column=0, sticky="nsew")
        self._main_frame.columnconfigure(0, weight=1)
        self._main_frame.rowconfigure(0, weight=1)

        # Canvas
        self.canvas = tk.Canvas(
            self._main_frame, width=cw, height=ch,
            cursor="crosshair", bg="#1a1a1a",
            highlightthickness=1, highlightbackground="#555"
        )
        self.canvas.grid(row=0, column=0)

        # Datei-Auswahl-Frame (wird nur in Schritt 0 angezeigt)
        self._files_frame = ttk.Frame(self._main_frame, padding=20)
        self._files_frame.grid(row=0, column=0, sticky="nw")
        self._files_frame.grid_remove()  # zunächst versteckt
        self._build_files_frame()

        # Buttons
        btn_frame = ttk.Frame(self, padding=(12, 8))
        btn_frame.grid(row=3, column=0, sticky="ew")
        self._back_btn = ttk.Button(btn_frame, text="◄  Zurück",
                                     command=self._back)
        self._back_btn.pack(side="left", padx=(0, 6))
        self._skip_btn = ttk.Button(btn_frame, text="Überspringen",
                                     command=self._skip)
        self._skip_btn.pack(side="left")
        ttk.Button(btn_frame, text="Abbrechen",
                   command=self.destroy).pack(side="right", padx=(6, 0))
        self._next_btn = ttk.Button(btn_frame, text="Weiter  ►",
                                     command=self._next)
        self._next_btn.pack(side="right")

        self.geometry(f"{cw + 40}x{ch + 200}")

    def _build_files_frame(self):
        """Baut den Dateiauswahl-Bereich auf."""
        f = self._files_frame
        ttk.Label(f, text="Template-Bild (JPG/PNG):",
                  font=("TkDefaultFont", 10, "bold")).grid(
            row=0, column=0, sticky="w", pady=(0, 4))

        self._template_var = tk.StringVar(value=self._template_rel)
        ttk.Entry(f, textvariable=self._template_var, width=60).grid(
            row=1, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(f, text="📂  Durchsuchen",
                   command=self._browse_template).grid(row=1, column=1)

        ttk.Label(f, text="CSV-Datei (Tabellen-Daten):",
                  font=("TkDefaultFont", 10, "bold")).grid(
            row=2, column=0, sticky="w", pady=(20, 4))

        self._csv_var = tk.StringVar(value=self._csv_rel)
        ttk.Entry(f, textvariable=self._csv_var, width=60).grid(
            row=3, column=0, sticky="ew", padx=(0, 8))
        ttk.Button(f, text="📂  Durchsuchen",
                   command=self._browse_csv).grid(row=3, column=1)

        ttk.Label(
            f,
            text="Pfade können relativ zum Programmordner oder absolut sein.\n"
                 "Nach dem Speichern wird das neue Template sofort geladen.",
            foreground="gray"
        ).grid(row=4, column=0, columnspan=2, sticky="w", pady=(12, 0))

    def _browse_template(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="Template-Bild auswählen",
            filetypes=[("Bilder", "*.jpg *.jpeg *.png *.bmp"), ("Alle Dateien", "*.*")],
            initialdir=self._app_dir,
        )
        if path:
            try:
                rel = Path(path).relative_to(self._app_dir)
                self._template_var.set(str(rel))
            except ValueError:
                self._template_var.set(path)  # absoluter Pfad wenn außerhalb

    def _browse_csv(self):
        path = filedialog.askopenfilename(
            parent=self,
            title="CSV-Datei auswählen",
            filetypes=[("CSV-Dateien", "*.csv"), ("Alle Dateien", "*.*")],
            initialdir=self._app_dir,
        )
        if path:
            try:
                rel = Path(path).relative_to(self._app_dir)
                self._csv_var.set(str(rel))
            except ValueError:
                self._csv_var.set(path)

    # ------------------------------------------------------------------
    # Schrittsteuerung
    # ------------------------------------------------------------------

    def _show_step(self):
        self._unbind_all()
        self._step_var.set(f"Schritt {self._step + 1} / {self._total_steps}")
        self._back_btn.configure(state="normal" if self._step > 0 else "disabled")
        self._next_btn.configure(text="Weiter  ►")
        self._skip_btn.pack()

        if self._step == self._STEP_FILES:
            self._show_files_step()
        elif 1 <= self._step <= self._n_fields:
            self._show_field_step(self._step - 1)
        elif self._step == self._step_attitude:
            self._show_attitude_step()
        elif self._step == self._step_adjust:
            self._show_adjust_step()

    def _show_files_step(self):
        self._title_var.set("Schritt 1: Dateipfade")
        self._inst_var.set(
            "Wähle das Template-Bild (Charakterbogen) und die CSV-Datei (Zufallstabellen) aus.\n"
            "Die aktuell gespeicherten Pfade sind bereits eingetragen. Klicke „Durchsuchen“, um eine Datei neu zu wählen."
        )
        self._skip_btn.pack_forget()
        self.canvas.grid_remove()
        self._files_frame.grid()

    def _show_field_step(self, field_index):
        self._files_frame.grid_remove()
        self.canvas.grid()
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_img)

        name = self.field_names[field_index]
        color = _FIELD_COLORS[field_index % len(_FIELD_COLORS)]
        self._title_var.set(f"Feld: {name}")
        self._inst_var.set(
            f"Ziehe mit der Maus eine neue Box für das Feld \"{name}\" auf dem Bogen auf.\n"
            "Linksklick + Ziehen = Box aufziehen.  "
            "Die bestehende Box wird grau gestrichelt angezeigt.  "
            "Klicke Überspringen, um die aktuelle Box beizubehalten."
        )
        self._draw_single_step(name, color)

    def _show_attitude_step(self):
        self._files_frame.grid_remove()
        self.canvas.grid()
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_img)

        self._title_var.set("Attitude-Marker: Kreispositionen festlegen")
        self._inst_var.set(
            f"Klicke auf dem Bogen, um die Mittelpunkte der Kreise zu setzen (aktuell {len(self._att_x)} Kreise).\n"
            "Rechtsklick auf einen Kreis entfernt ihn. Die Y-Koordinate und der Radius können unten angepasst werden."
        )
        self._next_btn.configure(text="Weiter  ►")
        self._skip_btn.pack()
        self._start_attitude_step()

    def _show_adjust_step(self):
        self._files_frame.grid_remove()
        self.canvas.grid()
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_img)

        self._title_var.set("Alle Felder prüfen und anpassen")
        self._inst_var.set(
            "Alle Felder und Attitude-Marker werden gleichzeitig angezeigt.\n"
            "Box verschieben: auf die Box klicken und ziehen.  "
            "Größe ändern: an den kleinen Quadraten an den Ecken/Kanten ziehen.  "
            "Klicke dann auf Speichern."
        )
        self._next_btn.configure(text="💾  Speichern")
        self._skip_btn.pack_forget()
        self._start_adjust_step()

    def _next(self):
        if self._step == self._STEP_FILES:
            # Pfade übernehmen
            self._template_rel = self._template_var.get().strip()
            self._csv_rel = self._csv_var.get().strip()
            self._step += 1
            self._show_step()
        elif self._step <= self._n_fields:
            self._step += 1
            self._show_step()
        elif self._step == self._step_attitude:
            self._commit_attitude_controls()
            self._step += 1
            self._show_step()
        else:
            self._save_and_close()

    def _back(self):
        if self._step > 0:
            self._step -= 1
            self._show_step()

    def _skip(self):
        self._step += 1
        self._show_step()

    # ------------------------------------------------------------------
    # Einzelner Feld-Schritt – Box aufziehen
    # ------------------------------------------------------------------

    def _draw_single_step(self, name, color):
        s = self._scale
        existing = _scale_box(self.boxes[name], s)
        self.canvas.create_rectangle(
            *existing, outline="#888888", dash=(6, 4), width=2, tags="existing")
        self.canvas.create_text(
            existing[0] + 4, existing[1] + 4, anchor="nw",
            text=name, fill="#aaaaaa",
            font=("TkDefaultFont", 9), tags="existing")

        self._drag = {"active": False, "x0": 0, "y0": 0, "rect_id": None}

        def on_press(ev):
            self.canvas.delete("newbox")
            self._drag.update(active=True, x0=ev.x, y0=ev.y)
            rid = self.canvas.create_rectangle(
                ev.x, ev.y, ev.x, ev.y, outline=color, width=2, tags="newbox")
            self._drag["rect_id"] = rid

        def on_drag(ev):
            if not self._drag["active"]:
                return
            self.canvas.coords(
                self._drag["rect_id"],
                self._drag["x0"], self._drag["y0"], ev.x, ev.y)

        def on_release(ev):
            if not self._drag["active"]:
                return
            self._drag["active"] = False
            x0, y0 = self._drag["x0"], self._drag["y0"]
            x1, y1 = ev.x, ev.y
            cx1, cx2 = sorted([x0, x1])
            cy1, cy2 = sorted([y0, y1])
            if (cx2 - cx1) < _MIN_BOX or (cy2 - cy1) < _MIN_BOX:
                messagebox.showwarning(
                    "Box zu klein",
                    "Die Box ist zu klein. Bitte erneut aufziehen.",
                    parent=self)
                self.canvas.delete("newbox")
                return
            self.boxes[name] = _unscale_box([cx1, cy1, cx2, cy2], s)
            self.canvas.delete("newbox")
            self.canvas.create_rectangle(
                cx1, cy1, cx2, cy2, outline=color, width=2, tags="newbox")
            self.canvas.create_text(
                cx1 + 4, cy1 + 4, anchor="nw",
                text=name, fill=color,
                font=("TkDefaultFont", 9, "bold"), tags="newbox")

        self.canvas.bind("<ButtonPress-1>", on_press)
        self.canvas.bind("<B1-Motion>", on_drag)
        self.canvas.bind("<ButtonRelease-1>", on_release)

    # ------------------------------------------------------------------
    # Attitude-Marker-Schritt
    # ------------------------------------------------------------------

    def _start_attitude_step(self):
        """Zeigt Kreise und erlaubt Klick-Setzen / Rechtsklick-Entfernen."""
        # Kontroll-Leiste unterhalb des Canvas einblenden
        if not hasattr(self, "_att_controls_frame"):
            self._att_controls_frame = ttk.LabelFrame(
                self, text="Attitude-Marker Einstellungen", padding=(10, 6))
            self._att_controls_frame.grid(
                row=4, column=0, sticky="ew", padx=12, pady=(0, 4))

            ttk.Label(self._att_controls_frame, text="Y-Position (Bildpixel):").grid(
                row=0, column=0, sticky="w", padx=(0, 6))
            self._att_y_var = tk.IntVar(value=self._att_y)
            ttk.Spinbox(self._att_controls_frame, textvariable=self._att_y_var,
                        from_=0, to=5000, width=8,
                        command=self._redraw_attitude).grid(row=0, column=1, padx=(0, 20))
            self._att_y_var.trace_add("write", lambda *_: self._redraw_attitude())

            ttk.Label(self._att_controls_frame, text="Radius (Bildpixel):").grid(
                row=0, column=2, sticky="w", padx=(0, 6))
            self._att_r_var = tk.IntVar(value=self._att_radius)
            ttk.Spinbox(self._att_controls_frame, textvariable=self._att_r_var,
                        from_=1, to=100, width=6,
                        command=self._redraw_attitude).grid(row=0, column=3, padx=(0, 20))
            self._att_r_var.trace_add("write", lambda *_: self._redraw_attitude())

            ttk.Label(self._att_controls_frame, text="Liniensstärke:").grid(
                row=0, column=4, sticky="w", padx=(0, 6))
            self._att_lw_var = tk.IntVar(value=self._att_line_width)
            ttk.Spinbox(self._att_controls_frame, textvariable=self._att_lw_var,
                        from_=1, to=20, width=5,
                        command=self._redraw_attitude).grid(row=0, column=5, padx=(0, 20))
            self._att_lw_var.trace_add("write", lambda *_: self._redraw_attitude())

            self._att_count_var = tk.StringVar()
            ttk.Label(self._att_controls_frame,
                      textvariable=self._att_count_var,
                      foreground="gray").grid(row=0, column=6, sticky="w")
        else:
            self._att_controls_frame.grid()  # wieder einblenden
            self._att_y_var.set(self._att_y)
            self._att_r_var.set(self._att_radius)
            self._att_lw_var.set(self._att_line_width)

        self._redraw_attitude()

        self.canvas.bind("<ButtonPress-1>", self._att_click)
        self.canvas.bind("<ButtonPress-3>", self._att_right_click)

    def _att_click(self, ev):
        """Linksklick: neuen Kreis-Mittelpunkt an X-Position hinzufügen."""
        s = self._scale
        img_x = int(ev.x / s)
        self._att_x.append(img_x)
        self._att_x.sort()
        self._redraw_attitude()

    def _att_right_click(self, ev):
        """Rechtsklick: nächsten Kreis entfernen."""
        if not self._att_x:
            return
        s = self._scale
        canvas_positions = [int(x * s) for x in self._att_x]
        # nächsten Kreis zum Klickpunkt finden
        closest = min(range(len(canvas_positions)),
                      key=lambda i: abs(canvas_positions[i] - ev.x))
        self._att_x.pop(closest)
        self._redraw_attitude()

    def _redraw_attitude(self):
        """Zeichnet alle Attitude-Marker neu auf dem Canvas."""
        self.canvas.delete("attitude")
        try:
            cy = int(self._att_y_var.get() * self._scale)
            cr = max(1, int(self._att_r_var.get() * self._scale))
        except (tk.TclError, ValueError):
            return

        for i, img_x in enumerate(self._att_x):
            cx = int(img_x * self._scale)
            self.canvas.create_oval(
                cx - cr, cy - cr, cx + cr, cy + cr,
                outline=_ATTITUDE_COLOR, width=2, tags="attitude")
            self.canvas.create_text(
                cx, cy + cr + 10, text=str(i + 1),
                fill=_ATTITUDE_COLOR, font=("TkDefaultFont", 8),
                tags="attitude")

        count = len(self._att_x)
        self._att_count_var.set(f"{count} Kreis{'e' if count != 1 else ''}")

    def _commit_attitude_controls(self):
        """Liest die Spinbox-Werte aus und speichert sie intern."""
        try:
            self._att_y = int(self._att_y_var.get())
            self._att_radius = int(self._att_r_var.get())
            self._att_line_width = int(self._att_lw_var.get())
        except (tk.TclError, ValueError):
            pass
        if hasattr(self, "_att_controls_frame"):
            self._att_controls_frame.grid_remove()

    # ------------------------------------------------------------------
    # Abschluss-Schritt – alle Boxen gleichzeitig anpassen
    # ------------------------------------------------------------------

    def _start_adjust_step(self):
        s = self._scale
        self._adj_boxes = {n: _scale_box(self.boxes[n], s)
                           for n in self.field_names}
        self._adj_rects = {}
        self._adj_labels = {}
        self._adj_handles = {}
        self._adj_active = None

        for i, name in enumerate(self.field_names):
            self._draw_adj_box(name)

        # Attitude-Marker im Adjust-Schritt schreibgeschützt einblenden
        self._draw_attitude_readonly()

        self.canvas.bind("<ButtonPress-1>", self._adj_press)
        self.canvas.bind("<B1-Motion>", self._adj_drag)
        self.canvas.bind("<ButtonRelease-1>", self._adj_release)
        self.canvas.config(cursor="arrow")

    def _draw_attitude_readonly(self):
        """Zeichnet Attitude-Marker (schreibgeschützt) im Adjust-Schritt."""
        self.canvas.delete("attitude_ro")
        cy = int(self._att_y * self._scale)
        cr = max(1, int(self._att_radius * self._scale))
        for i, img_x in enumerate(self._att_x):
            cx = int(img_x * self._scale)
            self.canvas.create_oval(
                cx - cr, cy - cr, cx + cr, cy + cr,
                outline=_ATTITUDE_COLOR, width=2, dash=(4, 3),
                tags="attitude_ro")
            self.canvas.create_text(
                cx, cy + cr + 10, text=str(i + 1),
                fill=_ATTITUDE_COLOR, font=("TkDefaultFont", 8),
                tags="attitude_ro")

    def _draw_adj_box(self, name, redraw=False):
        if redraw:
            self.canvas.delete(f"box_{name}")
            self.canvas.delete(f"lbl_{name}")
            for hid in list(self._adj_handles.get(name, {}).keys()):
                self.canvas.delete(hid)
            self._adj_handles[name] = {}

        b = self._adj_boxes[name]
        color = _FIELD_COLORS[self.field_names.index(name) % len(_FIELD_COLORS)]
        x1, y1, x2, y2 = b

        rid = self.canvas.create_rectangle(
            x1, y1, x2, y2,
            outline=color, width=2, fill="",
            tags=(f"box_{name}", "adj_box"))
        self._adj_rects[name] = rid

        lid = self.canvas.create_text(
            x1 + 4, y1 + 4, anchor="nw",
            text=name, fill=color,
            font=("TkDefaultFont", 9, "bold"),
            tags=(f"lbl_{name}", "adj_lbl"))
        self._adj_labels[name] = lid

        hs = _HANDLE_SIZE
        mx, my = (x1 + x2) // 2, (y1 + y2) // 2
        handle_positions = {
            "nw": (x1, y1), "n": (mx, y1), "ne": (x2, y1),
            "e":  (x2, my),
            "se": (x2, y2), "s": (mx, y2), "sw": (x1, y2),
            "w":  (x1, my),
        }
        self._adj_handles.setdefault(name, {})
        for edge, (hx, hy) in handle_positions.items():
            hid = self.canvas.create_rectangle(
                hx - hs, hy - hs, hx + hs, hy + hs,
                fill=color, outline="white", width=1,
                tags=(f"handle_{name}_{edge}", "adj_handle"))
            self._adj_handles[name][hid] = edge

    def _adj_press(self, ev):
        items = self.canvas.find_overlapping(
            ev.x - 4, ev.y - 4, ev.x + 4, ev.y + 4)
        for item in reversed(items):
            tags = self.canvas.gettags(item)
            for tag in tags:
                if tag.startswith("handle_"):
                    rest = tag[len("handle_"):]
                    edge = rest.rsplit("_", 1)[-1]
                    name = rest.rsplit("_", 1)[0]
                    if name in self.field_names:
                        self._adj_active = {
                            "type": "resize", "name": name,
                            "edge": edge, "lx": ev.x, "ly": ev.y}
                        return
        for item in reversed(items):
            tags = self.canvas.gettags(item)
            for tag in tags:
                if tag.startswith("box_"):
                    name = tag[4:]
                    if name in self.field_names:
                        self._adj_active = {
                            "type": "move", "name": name,
                            "lx": ev.x, "ly": ev.y}
                        return

    def _adj_drag(self, ev):
        if not self._adj_active:
            return
        a = self._adj_active
        dx = ev.x - a["lx"]
        dy = ev.y - a["ly"]
        a["lx"], a["ly"] = ev.x, ev.y
        name = a["name"]
        x1, y1, x2, y2 = self._adj_boxes[name]

        if a["type"] == "move":
            x1 += dx; y1 += dy; x2 += dx; y2 += dy
        elif a["type"] == "resize":
            edge = a["edge"]
            if "w" in edge: x1 += dx
            if "e" in edge: x2 += dx
            if "n" in edge: y1 += dy
            if "s" in edge: y2 += dy
            if x2 - x1 < _MIN_BOX:
                x1 = x2 - _MIN_BOX if "w" in edge else None
                if x1 is None: x2 = x1 + _MIN_BOX  # type: ignore
            if y2 - y1 < _MIN_BOX:
                y1 = y2 - _MIN_BOX if "n" in edge else None
                if y1 is None: y2 = y1 + _MIN_BOX  # type: ignore

        self._adj_boxes[name] = [x1, y1, x2, y2]
        self._draw_adj_box(name, redraw=True)

    def _adj_release(self, ev):
        self._adj_active = None

    # ------------------------------------------------------------------
    # Unbinden, Speichern
    # ------------------------------------------------------------------

    def _unbind_all(self):
        for seq in ("<ButtonPress-1>", "<B1-Motion>", "<ButtonRelease-1>",
                    "<ButtonPress-3>"):
            self.canvas.unbind(seq)
        if hasattr(self, "_att_controls_frame"):
            self._att_controls_frame.grid_remove()

    def _save_and_close(self):
        s = self._scale
        # Feld-Boxen
        for name in self.field_names:
            if hasattr(self, "_adj_boxes") and name in self._adj_boxes:
                self.boxes[name] = _unscale_box(self._adj_boxes[name], s)
            self.config_data["field_layouts"][name]["box"] = self.boxes[name]

        # Attitude-Marker
        self.config_data["attitude_markers"]["x_positions"] = self._att_x
        self.config_data["attitude_markers"]["y"] = self._att_y
        self.config_data["attitude_markers"]["radius"] = self._att_radius
        self.config_data["attitude_markers"]["line_width"] = self._att_line_width

        # Dateipfade
        self.config_data["template_file"] = self._template_rel
        self.config_data["csv_file"] = self._csv_rel

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo(
                "Gespeichert",
                "Alle Einstellungen wurden in config.json gespeichert.",
                parent=self)
        except Exception as exc:
            messagebox.showerror("Fehler beim Speichern", str(exc), parent=self)
            return

        self.destroy()
        if self.reload_callback:
            self.reload_callback()
