"""field_wizard.py

Mehrstufiger Wizard zum visuellen Festlegen der Feldkoordinaten
für den Charakterbogen.  Wird aus charbogen_gui.py heraus aufgerufen.

Ablauf
------
1. Für jedes Feld in config['field_layouts'] wird ein Schritt angezeigt,
   in dem der Benutzer auf dem Bogen-Canvas eine Box aufziehen kann.
2. Im letzten Schritt werden alle Boxen gleichzeitig dargestellt;
   einzelne Boxen lassen sich verschieben und in der Größe anpassen.
3. Auf Klick auf „Speichern" werden die neuen Koordinaten in config.json
   geschrieben und die übergebene reload_callback-Funktion aufgerufen.
"""

import json
import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path

from PIL import Image, ImageTk

# Farben für die einzelnen Felder (zyklisch)
_FIELD_COLORS = [
    "#e63946", "#2a9d8f", "#e9c46a", "#f4a261",
    "#457b9d", "#a8dadc", "#6a4c93", "#80b918",
]

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

    def __init__(self, parent, config, config_path, reload_callback):
        super().__init__(parent)
        self.title("Felder anpassen – Wizard")
        self.resizable(True, True)
        self.grab_set()  # modal

        self.config_data = config
        self.config_path = Path(config_path)
        self.reload_callback = reload_callback

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

        # Bild laden und Skalierungsfaktor berechnen
        template_path = Path(config_path).parent / config["template_file"]
        self._orig_img = Image.open(template_path).convert("RGB")
        self._scale = min(
            _CANVAS_MAX_W / self._orig_img.width,
            _CANVAS_MAX_H / self._orig_img.height,
            1.0,
        )
        cw = int(self._orig_img.width * self._scale)
        ch = int(self._orig_img.height * self._scale)
        self._canvas_img = self._orig_img.resize((cw, ch), Image.LANCZOS)
        self._tk_img = ImageTk.PhotoImage(self._canvas_img)

        self._step = 0  # 0 … len(field_names)-1 = Einzelschritte, dann Adjust
        self._total_steps = len(self.field_names) + 1  # +1 für Adjust-Schritt

        self._build_ui(cw, ch)
        self._show_step()

    # ------------------------------------------------------------------
    # UI-Aufbau
    # ------------------------------------------------------------------

    def _build_ui(self, cw, ch):
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

        # Canvas
        canvas_frame = ttk.Frame(self, padding=(12, 6))
        canvas_frame.grid(row=2, column=0, sticky="nsew")
        self.canvas = tk.Canvas(
            canvas_frame, width=cw, height=ch,
            cursor="crosshair", bg="#1a1a1a",
            highlightthickness=1, highlightbackground="#555"
        )
        self.canvas.pack()

        # Buttons
        btn_frame = ttk.Frame(self, padding=(12, 8))
        btn_frame.grid(row=3, column=0, sticky="ew")
        self._back_btn = ttk.Button(btn_frame, text="◀  Zurück",
                                     command=self._back)
        self._back_btn.pack(side="left", padx=(0, 6))
        self._skip_btn = ttk.Button(btn_frame, text="Überspringen",
                                     command=self._skip)
        self._skip_btn.pack(side="left")
        ttk.Button(btn_frame, text="Abbrechen",
                   command=self.destroy).pack(side="right", padx=(6, 0))
        self._next_btn = ttk.Button(btn_frame, text="Weiter  ▶",
                                     command=self._next)
        self._next_btn.pack(side="right")

        self.geometry(f"{cw + 40}x{ch + 160}")

    # ------------------------------------------------------------------
    # Schrittsteuerung
    # ------------------------------------------------------------------

    def _show_step(self):
        self._unbind_all()
        self.canvas.delete("all")
        self.canvas.create_image(0, 0, anchor="nw", image=self._tk_img)

        n = len(self.field_names)
        self._step_var.set(f"Schritt {self._step + 1} / {self._total_steps}")
        self._back_btn.configure(state="normal" if self._step > 0 else "disabled")

        if self._step < n:
            # Einzelner Feld-Schritt
            name = self.field_names[self._step]
            color = _FIELD_COLORS[self._step % len(_FIELD_COLORS)]
            self._title_var.set(f"Feld: {name}")
            self._inst_var.set(
                f"Ziehe mit der Maus eine neue Box für das Feld \"{name}\" auf dem Bogen auf.\n"
                "Linksklick + Ziehen = Box aufziehen.  "
                "Die bestehende Box wird grau gestrichelt angezeigt.  "
                "Klicke Überspringen, um die aktuelle Box beizubehalten."
            )
            self._next_btn.configure(text="Weiter  ▶")
            self._skip_btn.pack()
            self._draw_single_step(name, color)
        else:
            # Abschluss-Schritt: alle Boxen gleichzeitig anpassen
            self._title_var.set("Alle Felder prüfen und anpassen")
            self._inst_var.set(
                "Alle Felder werden gleichzeitig angezeigt.\n"
                "Box verschieben: auf die Box klicken und ziehen.  "
                "Größe ändern: an den kleinen Quadraten an den Ecken/Kanten ziehen.  "
                "Klicke dann auf Speichern."
            )
            self._next_btn.configure(text="💾  Speichern")
            self._skip_btn.pack_forget()
            self._start_adjust_step()

    def _next(self):
        if self._step < len(self.field_names):
            self._step += 1
            self._show_step()
        else:
            self._save_and_close()

    def _back(self):
        if self._step > 0:
            self._step -= 1
            self._show_step()

    def _skip(self):
        """Aktuelles Feld überspringen (Box bleibt unverändert)."""
        self._step += 1
        self._show_step()

    # ------------------------------------------------------------------
    # Einzelner Feld-Schritt – Box aufziehen
    # ------------------------------------------------------------------

    def _draw_single_step(self, name, color):
        """Zeigt bestehende Box (grau) und erlaubt Aufziehen einer neuen."""
        s = self._scale
        # bestehende Box grau gestrichelt
        existing = _scale_box(self.boxes[name], s)
        self.canvas.create_rectangle(
            *existing, outline="#888888", dash=(6, 4), width=2,
            tags="existing"
        )
        self.canvas.create_text(
            existing[0] + 4, existing[1] + 4,
            anchor="nw", text=name, fill="#aaaaaa",
            font=("TkDefaultFont", 9), tags="existing"
        )

        # Zustand für Drag
        self._drag = {"active": False, "x0": 0, "y0": 0, "rect_id": None}

        def on_press(ev):
            self.canvas.delete("newbox")
            self._drag.update(active=True, x0=ev.x, y0=ev.y)
            rid = self.canvas.create_rectangle(
                ev.x, ev.y, ev.x, ev.y,
                outline=color, width=2, tags="newbox"
            )
            self._drag["rect_id"] = rid

        def on_drag(ev):
            if not self._drag["active"]:
                return
            self.canvas.coords(
                self._drag["rect_id"],
                self._drag["x0"], self._drag["y0"], ev.x, ev.y
            )

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
                    parent=self
                )
                self.canvas.delete("newbox")
                return
            self.boxes[name] = _unscale_box([cx1, cy1, cx2, cy2], s)
            self.canvas.create_rectangle(
                cx1, cy1, cx2, cy2,
                outline=color, width=2, tags="newbox"
            )
            self.canvas.create_text(
                cx1 + 4, cy1 + 4, anchor="nw",
                text=name, fill=color,
                font=("TkDefaultFont", 9, "bold"), tags="newbox"
            )

        self.canvas.bind("<ButtonPress-1>", on_press)
        self.canvas.bind("<B1-Motion>", on_drag)
        self.canvas.bind("<ButtonRelease-1>", on_release)

    # ------------------------------------------------------------------
    # Abschluss-Schritt – alle Boxen gleichzeitig anpassen
    # ------------------------------------------------------------------

    def _start_adjust_step(self):
        """Zeichnet alle Boxen mit Handles; erlaubt Verschieben + Resize."""
        s = self._scale
        self._adj_boxes = {n: _scale_box(self.boxes[n], s)
                           for n in self.field_names}
        self._adj_rects = {}
        self._adj_labels = {}
        self._adj_handles = {}
        self._adj_active = None

        for i, name in enumerate(self.field_names):
            color = _FIELD_COLORS[i % len(_FIELD_COLORS)]
            self._draw_adj_box(name, color)

        self.canvas.bind("<ButtonPress-1>", self._adj_press)
        self.canvas.bind("<B1-Motion>", self._adj_drag)
        self.canvas.bind("<ButtonRelease-1>", self._adj_release)
        self.canvas.config(cursor="arrow")

    def _draw_adj_box(self, name, color, redraw=False):
        """Zeichnet Box + Label + Handles für ein Feld."""
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
            tags=(f"box_{name}", "adj_box")
        )
        self._adj_rects[name] = rid

        lid = self.canvas.create_text(
            x1 + 4, y1 + 4, anchor="nw",
            text=name, fill=color,
            font=("TkDefaultFont", 9, "bold"),
            tags=(f"lbl_{name}", "adj_lbl")
        )
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
                tags=(f"handle_{name}_{edge}", "adj_handle")
            )
            self._adj_handles[name][hid] = edge

    # --- Drag-Logik für Adjust-Schritt ---

    def _adj_press(self, ev):
        items = self.canvas.find_overlapping(
            ev.x - 4, ev.y - 4, ev.x + 4, ev.y + 4
        )
        # Handle hat Vorrang vor Box
        for item in reversed(items):
            tags = self.canvas.gettags(item)
            for tag in tags:
                if tag.startswith("handle_"):
                    # handle_<name>_<edge> — name kann Leerzeichen enthalten,
                    # daher vom Ende her splitten
                    rest = tag[len("handle_"):]
                    edge = rest.rsplit("_", 1)[-1]
                    name = rest.rsplit("_", 1)[0]
                    if name in self.field_names:
                        self._adj_active = {
                            "type": "resize", "name": name,
                            "edge": edge, "lx": ev.x, "ly": ev.y
                        }
                        return
        for item in reversed(items):
            tags = self.canvas.gettags(item)
            for tag in tags:
                if tag.startswith("box_"):
                    name = tag[4:]
                    if name in self.field_names:
                        self._adj_active = {
                            "type": "move", "name": name,
                            "lx": ev.x, "ly": ev.y
                        }
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
                if "w" in edge: x1 = x2 - _MIN_BOX
                else:           x2 = x1 + _MIN_BOX
            if y2 - y1 < _MIN_BOX:
                if "n" in edge: y1 = y2 - _MIN_BOX
                else:           y2 = y1 + _MIN_BOX

        self._adj_boxes[name] = [x1, y1, x2, y2]
        self._draw_adj_box(name, None, redraw=True)

    def _adj_release(self, ev):
        self._adj_active = None

    # ------------------------------------------------------------------
    # Unbinden, Speichern
    # ------------------------------------------------------------------

    def _unbind_all(self):
        for seq in ("<ButtonPress-1>", "<B1-Motion>", "<ButtonRelease-1>"):
            self.canvas.unbind(seq)

    def _save_and_close(self):
        s = self._scale
        for name in self.field_names:
            if hasattr(self, "_adj_boxes") and name in self._adj_boxes:
                self.boxes[name] = _unscale_box(self._adj_boxes[name], s)
            self.config_data["field_layouts"][name]["box"] = self.boxes[name]

        try:
            with open(self.config_path, "w", encoding="utf-8") as f:
                json.dump(self.config_data, f, ensure_ascii=False, indent=2)
            messagebox.showinfo(
                "Gespeichert",
                "Die Feldkoordinaten wurden in config.json gespeichert.",
                parent=self
            )
        except Exception as exc:
            messagebox.showerror("Fehler beim Speichern", str(exc), parent=self)
            return

        self.destroy()
        if self.reload_callback:
            self.reload_callback()
