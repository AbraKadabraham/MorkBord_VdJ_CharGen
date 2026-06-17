import csv
import json
import math
import random
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageDraw, ImageFont, ImageTk

from field_wizard import FieldWizard, _find_font_path

APP_DIR = Path(__file__).resolve().parent

# Systeme: Anzeigename -> Config-Datei
SYSTEMS = {
    'Vorzimmer des Jenseits': 'config.json',
    'Mörk Borg':              'config_mb.json',
}

MB_CONFIG_FILE = 'config_mb.json'

_ABILITY_MOD_TABLE = [
    (4,  -3),
    (6,  -2),
    (8,  -1),
    (12,  0),
    (14, +1),
    (16, +2),
    (20, +3),
]


def _sum_to_mod(total: int) -> int:
    for threshold, mod in _ABILITY_MOD_TABLE:
        if total <= threshold:
            return mod
    return +3


def _roll_ability(rng: random.Random, use_4d6_drop: bool = False) -> int:
    if use_4d6_drop:
        rolls = [rng.randint(1, 6) for _ in range(4)]
        total = sum(rolls) - min(rolls)
    else:
        total = sum(rng.randint(1, 6) for _ in range(3))
    return _sum_to_mod(total)


def _format_mod(mod: int) -> str:
    if mod > 0:
        return f'+{mod}'
    return str(mod)


def next_free_path(directory, stem, suffix):
    directory = Path(directory)
    candidate = directory / f'{stem}{suffix}'
    if not candidate.exists():
        return candidate
    index = 2
    while True:
        candidate = directory / f'{stem}_{index}{suffix}'
        if not candidate.exists():
            return candidate
        index += 1


class ColumnPool:
    def __init__(self, values, rng):
        self.all_values = [v.strip() for v in values if v and v.strip()]
        self.rng = rng
        self.remaining = []
        self._refill()

    def _refill(self):
        self.remaining = self.all_values[:]
        self.rng.shuffle(self.remaining)

    def draw(self):
        if not self.all_values:
            return ''
        if not self.remaining:
            self._refill()
        return self.remaining.pop()


class CharacterGenerator:
    def __init__(self, config):
        self.columns = {}
        self.missing_files = []
        self.reload_from_config(config)

    def reload_from_config(self, config):
        self.config = config
        self.template_path = (APP_DIR / config['template_file']).resolve()
        self.csv_path = (APP_DIR / config['csv_file']).resolve()
        self.field_mapping = config['field_mapping']
        self.field_layouts = config['field_layouts']
        self.attitude = config.get('attitude_markers')
        self.conditional_logic = config.get('conditional_logic', {})
        self.scroll_fields = config.get('scroll_fields', {})
        self.a4 = tuple(config['a4_size'])
        self.debug = config.get('debug', {})

        self.missing_files = []
        if not self.template_path.exists():
            self.missing_files.append(('Template-Bild', str(self.template_path)))
        if not self.csv_path.exists():
            self.missing_files.append(('CSV-Datei', str(self.csv_path)))

        if not self.csv_path.exists():
            self.columns = {}
        else:
            self.columns = self.load_csv_columns(self.csv_path)

    def _is_mb_system(self) -> bool:
        cfg_file = self.config.get('csv_file', '')
        tmpl_file = self.config.get('template_file', '')
        return 'mb' in Path(cfg_file).stem.lower() or 'mb' in Path(tmpl_file).stem.lower()

    def is_ready(self):
        return len(self.missing_files) == 0

    def load_csv_columns(self, csv_path):
        encodings = ['utf-8-sig', 'utf-8', 'cp1252', 'latin-1']
        rows = None
        last_error = None
        for encoding in encodings:
            try:
                with open(csv_path, 'r', encoding=encoding, newline='') as f:
                    rows = list(csv.DictReader(f, delimiter=';'))
                break
            except UnicodeDecodeError as e:
                last_error = e
        if rows is None:
            raise ValueError(
                f'CSV konnte nicht gelesen werden. Letzter Fehler: {last_error}'
            )
        columns = {}
        for row in rows:
            for key, value in row.items():
                if key is None:
                    continue
                columns.setdefault(key, [])
                text = (value or '').strip()
                if text:
                    columns[key].append(text)
        return columns

    def _needed_columns(self):
        needed = set()
        for v in self.field_mapping.values():
            if v is None:
                continue
            if isinstance(v, list):
                for col in v:
                    needed.add(col)
            else:
                needed.add(v)
        for block in self.conditional_logic.values():
            for rule in block.get('rules', []):
                col = rule.get('draw_from')
                if col:
                    needed.add(col)
            for key in ('then_draw_from', 'else_draw_from'):
                col = block.get(key)
                if col:
                    needed.add(col)
        for scroll_def in self.scroll_fields.values():
            for entry in scroll_def.get('scrolls', []):
                needed.add(entry['name_column'])
                needed.add(entry['desc_column'])
        return needed

    def build_pools(self, rng):
        pools = {}
        for col in self._needed_columns():
            if col not in self.columns:
                raise ValueError(f'Spalte fehlt in CSV: {col}')
            pools[col] = ColumnPool(self.columns[col], rng)
        return pools

    def find_font(self, size, font_file=''):
        if font_file:
            path = _find_font_path(font_file, APP_DIR)
            if path:
                try:
                    return ImageFont.truetype(str(path), size=size)
                except Exception:
                    pass

        candidates = [
            APP_DIR / 'fonts' / 'DejaVuSerif.ttf',
            Path('/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf'),
            Path('/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'),
            Path('C:/Windows/Fonts/times.ttf'),
            Path('C:/Windows/Fonts/georgia.ttf'),
            Path('C:/Windows/Fonts/arial.ttf'),
        ]
        for path in candidates:
            if path.exists():
                return ImageFont.truetype(str(path), size=size)
        return ImageFont.load_default()

    def wrap_text(self, draw, text, font, max_width):
        words = text.split()
        lines = []
        current = ''
        for word in words:
            test = (current + ' ' + word).strip()
            bbox = draw.textbbox((0, 0), test, font=font)
            width = bbox[2] - bbox[0]
            if width <= max_width:
                current = test
            else:
                if current:
                    lines.append(current)
                current = word
        if current:
            lines.append(current)
        return lines

    def fit_and_draw(self, draw, box, text, start_size, align='left', font_file='',
                     valign='top'):
        x1, y1, x2, y2 = box
        max_width  = x2 - x1
        max_height = y2 - y1
        size       = start_size
        min_size   = self.config.get('min_font_size', 14)

        while size >= min_size:
            font      = self.find_font(size, font_file)
            raw_lines = text.split('\n')
            all_lines = []
            for raw in raw_lines:
                if raw.strip():
                    all_lines.extend(self.wrap_text(draw, raw, font, max_width - 8))
                else:
                    all_lines.append('')

            line_box    = draw.textbbox((0, 0), 'Ag', font=font)
            line_height = (line_box[3] - line_box[1]) + self.config.get('line_spacing', 6)
            total_height = len(all_lines) * line_height

            if total_height <= max_height:
                top_padding = self.config.get('top_padding', 4)

                if valign == 'middle':
                    y = y1 + (max_height - total_height) // 2
                elif valign == 'bottom':
                    y = y2 - total_height - top_padding
                else:
                    y = y1 + top_padding

                for line in all_lines:
                    if line:
                        bbox  = draw.textbbox((0, 0), line, font=font)
                        width = bbox[2] - bbox[0]
                        if align == 'center':
                            x = x1 + (max_width - width) // 2
                        elif align == 'right':
                            x = x2 - width - 4
                        else:
                            x = x1 + 4
                        draw.text((x, y), line, fill='black', font=font)
                    y += line_height
                return
            size -= 1

    def fit_and_draw_scrolls(self, draw, box, scroll_entries, heading_size,
                              desc_size_ratio, align='left', font_file='',
                              desc_font_file=''):
        x1, y1, x2, y2 = box
        max_width    = x2 - x1
        max_height   = y2 - y1
        min_size     = self.config.get('min_font_size', 14)
        line_spacing = self.config.get('line_spacing', 6)
        top_padding  = self.config.get('top_padding', 4)
        entry_gap    = self.config.get('scroll_entry_gap', 8)

        h_size = heading_size
        while h_size >= min_size:
            d_size = max(min_size, int(h_size * desc_size_ratio))
            h_font = self.find_font(h_size, font_file)
            d_font = self.find_font(d_size, desc_font_file or font_file)

            h_lh = (draw.textbbox((0, 0), 'Ag', font=h_font)[3]
                    - draw.textbbox((0, 0), 'Ag', font=h_font)[1]) + line_spacing
            d_lh = (draw.textbbox((0, 0), 'Ag', font=d_font)[3]
                    - draw.textbbox((0, 0), 'Ag', font=d_font)[1]) + line_spacing

            total_h = top_padding
            segments = []
            for idx, (heading, desc) in enumerate(scroll_entries):
                h_lines = self.wrap_text(draw, heading, h_font, max_width - 8)
                d_lines = self.wrap_text(draw, desc, d_font, max_width - 8) if desc else []
                if idx > 0:
                    total_h += entry_gap
                total_h += len(h_lines) * h_lh + len(d_lines) * d_lh
                segments.append((h_lines, d_lines))

            if total_h <= max_height:
                y = y1 + top_padding
                for idx, (h_lines, d_lines) in enumerate(segments):
                    if idx > 0:
                        y += entry_gap
                    for line in h_lines:
                        bbox  = draw.textbbox((0, 0), line, font=h_font)
                        width = bbox[2] - bbox[0]
                        if align == 'center':
                            x = x1 + (max_width - width) // 2
                        elif align == 'right':
                            x = x2 - width - 4
                        else:
                            x = x1 + 4
                        draw.text((x, y), line, fill='black', font=h_font)
                        y += h_lh
                    for line in d_lines:
                        bbox  = draw.textbbox((0, 0), line, font=d_font)
                        width = bbox[2] - bbox[0]
                        if align == 'center':
                            x = x1 + (max_width - width) // 2
                        elif align == 'right':
                            x = x2 - width - 4
                        else:
                            x = x1 + 4
                        draw.text((x, y), line, fill='black', font=d_font)
                        y += d_lh
                return
            h_size -= 1

    def draw_debug_overlay(self, draw):
        if not self.debug.get('enabled', False):
            return
        field_color = self.debug.get('field_box_color', '#ff0000')
        label_color = self.debug.get('label_color', '#0000ff')
        cross_color = self.debug.get('attitude_color', '#008000')
        width = self.debug.get('field_box_width', 3)
        label_font = self.find_font(self.debug.get('label_font_size', 18))
        for field_name, layout in self.field_layouts.items():
            box = tuple(layout['box'])
            draw.rectangle(box, outline=field_color, width=width)
            label_text = f"{field_name} {list(box)}"
            label_pos = (box[0] + 4, max(0, box[1] - 22))
            draw.text(label_pos, label_text, fill=label_color, font=label_font)
        if self.attitude:
            y = self.attitude['y']
            radius = self.attitude['radius']
            for i, x in enumerate(self.attitude['x_positions'], start=1):
                draw.ellipse((x - radius, y - radius, x + radius, y + radius),
                             outline=cross_color, width=2)
                draw.text((x - 8, y + radius + 4), str(i),
                          fill=cross_color, font=label_font)

    def generate_mb_stats(self, rng: random.Random) -> dict:
        attr_names = ['Stärke', 'Geschick', 'Präsenz', 'Zähigkeit']
        bonus_indices = set(rng.sample(range(4), 2))
        mods = {}
        for i, name in enumerate(attr_names):
            mods[name] = _roll_ability(rng, use_4d6_drop=(i in bonus_indices))
        toughness_mod = mods['Zähigkeit']
        hp     = max(1, toughness_mod + rng.randint(1, 8))
        omen   = rng.randint(1, 2)
        silver = (rng.randint(1, 6) + rng.randint(1, 6)) * 10
        return {
            'Stärke':         _format_mod(mods['Stärke']),
            'Geschick':       _format_mod(mods['Geschick']),
            'Präsenz':        _format_mod(mods['Präsenz']),
            'Zähigkeit':      _format_mod(mods['Zähigkeit']),
            'Trefferpunkte':  str(hp),
            'Omen':           str(omen),
            'Silber':         str(silver),
        }

    def generate_character(self, pools):
        character = {}

        # ── 1. Reguläres field_mapping ────────────────────────────────────
        for field_name, csv_column in self.field_mapping.items():
            if csv_column is None:
                character[field_name] = ''
            elif isinstance(csv_column, list):
                layout    = self.field_layouts.get(field_name, {})
                separator = layout.get('multi_column_separator', '\n')
                # skip_values: Liste von Strings, die nach dem Ziehen ignoriert werden
                # Vergleich case-insensitiv; Standard: ["nichts"] wenn skip_values nicht
                # gesetzt, aber nur angewendet wenn das Feld skip_values explizit hat.
                skip_raw  = layout.get('skip_values', [])
                skip_set  = {v.strip().lower() for v in skip_raw}
                parts = []
                for col in csv_column:
                    if col in pools:
                        val = pools[col].draw()
                        if skip_set and val.strip().lower() in skip_set:
                            continue  # diesen Wert überspringen
                        if val:
                            parts.append(val)
                character[field_name] = separator.join(parts)
            else:
                character[field_name] = pools[csv_column].draw()

        # ── 2. Conditional Logic ──────────────────────────────────────────
        for _block_name, block in self.conditional_logic.items():

            if 'source_field' in block and 'rules' in block:
                source_text = character.get(block['source_field'], '').lower()
                for rule in block['rules']:
                    trigger = rule.get('contains', '').lower()
                    if trigger and trigger in source_text:
                        draw_col = rule.get('draw_from', '')
                        target_field = rule.get('append_to', '')
                        if draw_col in pools and target_field:
                            drawn = pools[draw_col].draw()
                            if drawn:
                                existing = character.get(target_field, '')
                                if existing:
                                    character[target_field] = existing + '\n' + drawn
                                else:
                                    character[target_field] = drawn

            if 'if_field_nonempty' in block:
                check_field = block['if_field_nonempty']
                then_col    = block.get('then_draw_from', '')
                else_col    = block.get('else_draw_from', '')
                write_to    = block.get('write_to', '')
                if not write_to:
                    continue
                val = character.get(check_field)
                if isinstance(val, list):
                    field_has_content = len(val) > 0
                else:
                    field_has_content = bool((val or '').strip())
                chosen_col = then_col if field_has_content else else_col
                if chosen_col in pools:
                    character[write_to] = pools[chosen_col].draw()
                else:
                    character[write_to] = ''

        # ── 3. Schriftrolle-Felder (bedingt) ──────────────────────────────
        for field_name, scroll_def in self.scroll_fields.items():
            entries = []
            for scroll_entry in scroll_def.get('scrolls', []):
                name_col  = scroll_entry['name_column']
                desc_col  = scroll_entry['desc_column']
                label     = scroll_entry.get('label', name_col)

                check_field   = scroll_entry.get('only_if_field_contains', {}).get('field', '')
                trigger_text  = scroll_entry.get('only_if_field_contains', {}).get('contains', '')
                if check_field and trigger_text:
                    field_value = character.get(check_field, '')
                    if isinstance(field_value, list):
                        field_value = ' '.join(str(x) for x in field_value)
                    if trigger_text.lower() not in field_value.lower():
                        continue

                if name_col in pools:
                    scroll_name = pools[name_col].draw()
                    desc_text   = pools[desc_col].draw() if desc_col in pools else ''
                    if scroll_name:
                        heading = f"{label} \u2018{scroll_name}\u2019:"
                        entries.append((heading, desc_text))

            character[field_name] = entries

        # ── 4. MÖRK BORG: regelbasierte Stats ────────────────────────────
        if self._is_mb_system():
            pool_rng = next(iter(pools.values())).rng if pools else random.Random()
            mb_stats = self.generate_mb_stats(pool_rng)
            character.update(mb_stats)

        return character

    def render_sheet(self, character, rng):
        img  = Image.open(self.template_path).convert('RGB')
        draw = ImageDraw.Draw(img)

        for field_name, layout in self.field_layouts.items():
            box       = tuple(layout['box'])
            size      = layout['font_size']
            align     = layout.get('align',  'left')
            valign    = layout.get('valign', 'top')
            font_file = layout.get('font_file', '')
            value     = character.get(field_name)

            if field_name in self.scroll_fields:
                entries = value if isinstance(value, list) else []
                if entries:
                    desc_size_ratio = layout.get('desc_size_ratio', 0.8)
                    desc_font_file  = layout.get('desc_font_file', '')
                    self.fit_and_draw_scrolls(
                        draw, box, entries,
                        heading_size=size,
                        desc_size_ratio=desc_size_ratio,
                        align=align,
                        font_file=font_file,
                        desc_font_file=desc_font_file,
                    )
            else:
                if isinstance(value, str):
                    text = value.strip()
                else:
                    text = str(value).strip() if value else ''
                if text:
                    self.fit_and_draw(draw, box, text, size, align, font_file, valign)

        if self.attitude:
            idx = rng.randrange(len(self.attitude['x_positions']))
            cx  = self.attitude['x_positions'][idx]
            cy  = self.attitude['y']
            r   = self.attitude['radius']
            line_width = self.attitude['line_width']
            draw.line((cx - r, cy - r, cx + r, cy + r), fill='black', width=line_width)
            draw.line((cx - r, cy + r, cx + r, cy - r), fill='black', width=line_width)

        self.draw_debug_overlay(draw)
        return img

    def compose_a4_pages(self, images, output_dir, base_name):
        margin  = self.config['a4_layout']['margin']
        gap     = self.config['a4_layout']['gap']
        columns = 2
        rows    = 2
        cell_w  = (self.a4[0] - margin * 2 - gap * (columns - 1)) // columns
        cell_h  = (self.a4[1] - margin * 2 - gap * (rows - 1))    // rows
        positions = []
        for row in range(rows):
            for col in range(columns):
                x = margin + col * (cell_w + gap)
                y = margin + row * (cell_h + gap)
                positions.append((x, y))
        pages        = []
        total_pages  = math.ceil(len(images) / 4)
        for page_index in range(total_pages):
            page  = Image.new('RGB', self.a4, 'white')
            chunk = images[page_index * 4:(page_index + 1) * 4]
            for img, (x, y) in zip(chunk, positions):
                copy = img.copy()
                copy.thumbnail((cell_w, cell_h), Image.LANCZOS)
                px = x + (cell_w - copy.width)  // 2
                py = y + (cell_h - copy.height) // 2
                page.paste(copy, (px, py))
            page_stem = f'{base_name}_a4_page_{page_index + 1}'
            out_path  = next_free_path(output_dir, page_stem, '.png')
            page.save(out_path)
            pages.append(out_path)
        return pages

    def generate_batch(self, count, seed, output_dir, base_name='charbogen'):
        rng        = random.Random(seed)
        pools      = self.build_pools(rng)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        rendered     = []
        single_files = []
        for i in range(1, count + 1):
            character = self.generate_character(pools)
            img       = self.render_sheet(character, rng)
            stem      = f'{base_name}_{i:03d}'
            out_path  = next_free_path(output_dir, stem, '.png')
            img.save(out_path)
            single_files.append(out_path)
            rendered.append(img)
        a4_files = self.compose_a4_pages(rendered, output_dir, base_name)
        return single_files, a4_files

    def generate_preview(self, seed=None, pools=None):
        rng = random.Random(seed)
        if pools is None:
            pools = self.build_pools(rng)
        character = self.generate_character(pools)
        return self.render_sheet(character, rng)


class SettingsDialog(tk.Toplevel):
    def __init__(self, parent, config, config_path, reload_callback):
        super().__init__(parent)
        self.title('Einstellungen')
        self.resizable(False, False)
        self.grab_set()

        self._config      = config
        self._config_path = Path(config_path)
        self._app_dir     = self._config_path.parent
        self._reload_callback = reload_callback
        self._parent      = parent

        self._template_var = tk.StringVar(value=config.get('template_file', ''))
        self._csv_var      = tk.StringVar(value=config.get('csv_file', ''))

        self._build()

    def _build(self):
        paths_frame = ttk.LabelFrame(self, text='Dateipfade', padding=10)
        paths_frame.pack(fill='x', padx=14, pady=(14, 6))

        ttk.Label(paths_frame, text='Template-Bild (JPG/PNG):').grid(
            row=0, column=0, sticky='w', pady=(0, 2))
        ttk.Entry(paths_frame, textvariable=self._template_var, width=52).grid(
            row=1, column=0, sticky='ew', padx=(0, 8))
        ttk.Button(paths_frame, text='📂 Durchsuchen',
                   command=self._browse_template).grid(row=1, column=1)

        ttk.Label(paths_frame, text='CSV-Datei (Zufallstabellen):').grid(
            row=2, column=0, sticky='w', pady=(10, 2))
        ttk.Entry(paths_frame, textvariable=self._csv_var, width=52).grid(
            row=3, column=0, sticky='ew', padx=(0, 8))
        ttk.Button(paths_frame, text='📂 Durchsuchen',
                   command=self._browse_csv).grid(row=3, column=1)

        ttk.Label(
            paths_frame,
            text='Pfade können relativ zum Programmordner oder absolut sein.',
            foreground='gray'
        ).grid(row=4, column=0, columnspan=2, sticky='w', pady=(6, 0))

        fields_frame = ttk.LabelFrame(self, text='Felder & Marker', padding=10)
        fields_frame.pack(fill='x', padx=14, pady=6)

        ttk.Label(
            fields_frame,
            text='Position, Größe, Schriftgröße, Ausrichtung und Schriftart aller\n'
                 'Textfelder sowie die Attitude-Marker können visuell angepasst werden.'
        ).pack(anchor='w', pady=(0, 8))

        ttk.Button(
            fields_frame,
            text='🗺  Felder anpassen …',
            command=self._open_wizard
        ).pack(anchor='w')

        btn_frame = ttk.Frame(self, padding=(12, 8))
        btn_frame.pack(fill='x')
        ttk.Button(btn_frame, text='Abbrechen',
                   command=self.destroy).pack(side='right', padx=(6, 0))
        ttk.Button(btn_frame, text='💾  Speichern',
                   command=self._save).pack(side='right')

    def _browse_template(self):
        path = filedialog.askopenfilename(
            parent=self,
            title='Template-Bild auswählen',
            filetypes=[('Bilder', '*.jpg *.jpeg *.png *.bmp'), ('Alle Dateien', '*.*')],
            initialdir=self._app_dir,
        )
        if path:
            try:
                self._template_var.set(str(Path(path).relative_to(self._app_dir)))
            except ValueError:
                self._template_var.set(path)

    def _browse_csv(self):
        path = filedialog.askopenfilename(
            parent=self,
            title='CSV-Datei auswählen',
            filetypes=[('CSV-Dateien', '*.csv'), ('Alle Dateien', '*.*')],
            initialdir=self._app_dir,
        )
        if path:
            try:
                self._csv_var.set(str(Path(path).relative_to(self._app_dir)))
            except ValueError:
                self._csv_var.set(path)

    def _open_wizard(self):
        FieldWizard(
            parent=self,
            config=self._config,
            config_path=self._config_path,
            reload_callback=self._after_wizard_save,
        )

    def _after_wizard_save(self):
        self._reload_callback()
        try:
            with open(self._config_path, 'r', encoding='utf-8') as f:
                fresh = json.load(f)
            self._template_var.set(fresh.get('template_file', self._template_var.get()))
            self._csv_var.set(fresh.get('csv_file', self._csv_var.get()))
            self._config = fresh
        except Exception:
            pass

    def _save(self):
        self._config['template_file'] = self._template_var.get().strip()
        self._config['csv_file']      = self._csv_var.get().strip()
        try:
            with open(self._config_path, 'w', encoding='utf-8') as f:
                json.dump(self._config, f, ensure_ascii=False, indent=2)
        except Exception as exc:
            messagebox.showerror('Fehler beim Speichern', str(exc), parent=self)
            return
        self.destroy()
        self._reload_callback()


class App(tk.Tk):
    def __init__(self, generator, initial_system=None):
        super().__init__()
        self.generator = generator
        self.title('Charakterbogen Generator')
        self.geometry('1180x960')
        self.preview_photo = None
        self.current_preview_seed = None
        self.last_auto_seed       = None
        self.preview_pools        = None
        self._prev_pool_seed      = None
        self.debug_enabled = bool(self.generator.config.get('debug', {}).get('enabled', False))
        self._warning_bar  = None

        system_names           = list(SYSTEMS.keys())
        self._current_system   = initial_system if initial_system in SYSTEMS else system_names[0]

        self._build_ui()

        if self.generator.is_ready():
            self.refresh_preview()
        else:
            self._show_missing_files_warning()
            self.after(200, self.open_settings)

    def _build_ui(self):
        main = ttk.Frame(self, padding=12)
        main.pack(fill='both', expand=True)

        self._warning_bar = tk.Label(
            main,
            text='',
            background='#8b1a1a',
            foreground='white',
            font=('TkDefaultFont', 10, 'bold'),
            anchor='w',
            padx=10,
            pady=6,
        )

        top_bar = ttk.Frame(main)
        top_bar.pack(fill='x', pady=(0, 6))

        ttk.Label(top_bar, text='System:').pack(side='left', padx=(0, 6))
        self.system_var = tk.StringVar(value=self._current_system)
        system_combo = ttk.Combobox(
            top_bar,
            textvariable=self.system_var,
            values=list(SYSTEMS.keys()),
            state='readonly',
            width=28,
        )
        system_combo.pack(side='left', padx=(0, 12))
        system_combo.bind('<<ComboboxSelected>>', self._on_system_change)

        ttk.Button(
            top_bar,
            text='⚙  Einstellungen',
            command=self.open_settings,
        ).pack(side='left')

        info_text = (
            'Vorschau zeigt immer einen zufällig erzeugten Bogen. '
            'Das Seed-Feld zeigt den aktuell angezeigten Vorschau-Seed und kann auch manuell gesetzt werden.'
        )
        if self.debug_enabled:
            info_text += ' Debug-Modus aktiv: Feldrahmen und Marker werden eingeblendet.'
        ttk.Label(main, text=info_text).pack(fill='x', pady=(0, 6))

        preview_frame = ttk.LabelFrame(main, text='Vorschau', padding=10)
        preview_frame.pack(fill='both', expand=True)
        self.preview_label = ttk.Label(preview_frame)
        self.preview_label.pack(fill='both', expand=True)

        bottom_bar = ttk.Frame(main)
        bottom_bar.pack(fill='x', pady=(8, 4))

        ttk.Label(bottom_bar, text='Seed:').grid(row=0, column=0, sticky='w', padx=(0, 6))
        self.seed_var = tk.StringVar()
        ttk.Entry(bottom_bar, textvariable=self.seed_var, width=20).grid(
            row=0, column=1, sticky='w', padx=(0, 10))

        ttk.Button(bottom_bar, text='Aktualisieren',
                   command=self.refresh_preview).grid(row=0, column=2, sticky='w', padx=(0, 20))

        ttk.Label(bottom_bar, text='Anzahl Bögen:').grid(
            row=0, column=3, sticky='w', padx=(0, 6))
        self.count_var = tk.StringVar(value='4')
        ttk.Entry(bottom_bar, textvariable=self.count_var, width=10).grid(
            row=0, column=4, sticky='w', padx=(0, 10))

        ttk.Button(bottom_bar, text='Generieren',
                   command=self.generate_files).grid(row=0, column=5, sticky='w')

        if self.debug_enabled:
            ttk.Button(bottom_bar, text='JSON neu einlesen',
                       command=self.reload_config).grid(
                row=0, column=6, sticky='w', padx=(12, 0))

        self.status_var = tk.StringVar(value='Bereit.')
        ttk.Label(main, textvariable=self.status_var).pack(fill='x', pady=(2, 0))

    def _on_system_change(self, _event=None):
        selected = self.system_var.get()
        if selected == self._current_system:
            return
        self._current_system = selected
        config_file  = SYSTEMS[selected]
        config_path  = APP_DIR / config_file
        try:
            config = load_config(config_path)
            self.generator.reload_from_config(config)
        except FileNotFoundError:
            messagebox.showwarning(
                'Config nicht gefunden',
                f'Die Datei "{config_file}" wurde nicht gefunden.\n'
                'Bitte Einstellungen öffnen und Dateipfade hinterlegen.',
                parent=self,
            )
        except Exception as e:
            messagebox.showerror('Fehler beim Laden', str(e), parent=self)
            return
        self.preview_pools   = None
        self._prev_pool_seed = None
        self.seed_var.set('')
        self.last_auto_seed  = None
        if self.generator.is_ready():
            self._hide_warning_bar()
            self.refresh_preview()
            self.status_var.set(f'System gewechselt: {selected}')
        else:
            self._show_missing_files_warning()
            self.status_var.set(f'System "{selected}" – Dateien fehlen noch.')

    def _show_missing_files_warning(self):
        missing = self.generator.missing_files
        if not missing:
            if self._warning_bar:
                self._warning_bar.pack_forget()
            return
        lines = ['⚠  Fehlende Datei(en) – bitte in den Einstellungen verknüpfen:']
        for label, path in missing:
            lines.append(f'   • {label}: {path}')
        self._warning_bar.configure(text='\n'.join(lines))
        self._warning_bar.pack(fill='x', pady=(0, 6))

    def _hide_warning_bar(self):
        if self._warning_bar:
            self._warning_bar.pack_forget()

    def parse_seed(self):
        seed_text = self.seed_var.get().strip()
        if seed_text == '':
            return None
        try:
            return int(seed_text)
        except ValueError:
            raise ValueError('Der Seed muss eine ganze Zahl sein.')

    def determine_preview_seed(self):
        seed_text = self.seed_var.get().strip()
        if not seed_text:
            seed = random.randint(0, 2_147_483_647)
            return seed, False
        try:
            typed_seed = int(seed_text)
        except ValueError:
            raise ValueError('Der Seed muss eine ganze Zahl sein.')
        if self.last_auto_seed is not None and seed_text == str(self.last_auto_seed):
            seed = random.randint(0, 2_147_483_647)
            return seed, False
        return typed_seed, True

    def refresh_preview(self):
        if not self.generator.is_ready():
            self.status_var.set(
                'Vorschau nicht möglich – fehlende Dateien. Bitte Einstellungen öffnen.')
            return
        try:
            seed, user_locked = self.determine_preview_seed()
            if self.preview_pools is None or seed != self._prev_pool_seed:
                self.preview_pools   = self.generator.build_pools(random.Random(seed))
                self._prev_pool_seed = seed
            img = self.generator.generate_preview(seed, pools=self.preview_pools)
            self.current_preview_seed = seed
            self.seed_var.set(str(seed))
            if user_locked:
                self.last_auto_seed = None
            else:
                self.last_auto_seed = seed
            self.show_preview(img)
            mode = 'manuell' if user_locked else 'auto'
            self.status_var.set(f'Vorschau aktualisiert (Seed {seed}, {mode}).')
        except Exception as e:
            messagebox.showerror('Fehler', str(e))

    def show_preview(self, img):
        max_w, max_h = 1020, 780
        copy = img.copy()
        copy.thumbnail((max_w, max_h), Image.LANCZOS)
        self.preview_photo = ImageTk.PhotoImage(copy)
        self.preview_label.configure(image=self.preview_photo)

    def reload_config(self):
        config_path = APP_DIR / SYSTEMS[self._current_system]
        try:
            config = load_config(config_path)
            self.generator.reload_from_config(config)
            self.debug_enabled = bool(
                self.generator.config.get('debug', {}).get('enabled', False))
            self.preview_pools   = None
            self._prev_pool_seed = None
            if self.generator.is_ready():
                self._hide_warning_bar()
                self.refresh_preview()
                self.status_var.set('Konfiguration wurde neu eingelesen.')
            else:
                self._show_missing_files_warning()
                self.status_var.set(
                    'Konfiguration gespeichert – Dateien noch nicht gefunden.')
        except Exception as e:
            messagebox.showerror('Fehler beim Neueinlesen', str(e))

    def open_settings(self):
        config_path = APP_DIR / SYSTEMS[self._current_system]
        SettingsDialog(
            parent=self,
            config=self.generator.config,
            config_path=config_path,
            reload_callback=self.reload_config,
        )

    def generate_files(self):
        if not self.generator.is_ready():
            messagebox.showwarning(
                'Dateien fehlen',
                'Bitte zuerst alle Dateien in den Einstellungen verknüpfen.',
                parent=self)
            return
        try:
            seed  = self.parse_seed()
            count = int(self.count_var.get().strip())
            if count < 1:
                raise ValueError('Die Anzahl muss mindestens 1 sein.')
        except ValueError as e:
            messagebox.showerror('Fehler', str(e))
            return

        target_dir = filedialog.askdirectory(title='Zielordner zum Speichern auswählen')
        if not target_dir:
            return

        try:
            single_files, a4_files = self.generator.generate_batch(
                count, seed, target_dir)
            self.status_var.set(
                f'Erstellt: {len(single_files)} Einzeldateien, '
                f'{len(a4_files)} A4-Seiten in {target_dir}')
            messagebox.showinfo(
                'Fertig',
                f'{len(single_files)} Bögen und {len(a4_files)} A4-Seiten wurden gespeichert.')
        except Exception as e:
            messagebox.showerror('Fehler', str(e))


def load_config(path=None):
    if path is None:
        path = APP_DIR / 'config.json'
    with open(path, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    config    = load_config()
    generator = CharacterGenerator(config)
    app       = App(generator, initial_system=list(SYSTEMS.keys())[0])
    app.mainloop()


if __name__ == '__main__':
    main()
