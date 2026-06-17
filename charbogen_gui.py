import csv
import json
import math
import random
from pathlib import Path
import tkinter as tk
from tkinter import ttk, filedialog, messagebox
from PIL import Image, ImageDraw, ImageFont, ImageTk

APP_DIR = Path(__file__).resolve().parent
CONFIG_PATH = APP_DIR / 'config.json'


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
        self.reload_from_config(config)

    def reload_from_config(self, config):
        self.config = config
        self.template_path = (APP_DIR / config['template_file']).resolve()
        self.csv_path = (APP_DIR / config['csv_file']).resolve()
        self.field_mapping = config['field_mapping']
        self.field_layouts = config['field_layouts']
        self.attitude = config['attitude_markers']
        self.a4 = tuple(config['a4_size'])
        self.debug = config.get('debug', {})
        self.columns = self.load_csv_columns(self.csv_path)

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
                f'CSV konnte nicht gelesen werden. Bitte als UTF-8 oder ANSI/Windows-1252 speichern. Letzter Fehler: {last_error}'
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

    def build_pools(self, rng):
        pools = {}
        needed_columns = {v for v in self.field_mapping.values() if v}
        for col in needed_columns:
            if col not in self.columns:
                raise ValueError(f'Spalte fehlt in CSV: {col}')
            pools[col] = ColumnPool(self.columns[col], rng)
        return pools

    def find_font(self, size):
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

    def fit_and_draw(self, draw, box, text, start_size, align='left'):
        x1, y1, x2, y2 = box
        max_width = x2 - x1
        max_height = y2 - y1
        size = start_size
        min_size = self.config.get('min_font_size', 14)
        while size >= min_size:
            font = self.find_font(size)
            lines = self.wrap_text(draw, text, font, max_width - 8)
            line_box = draw.textbbox((0, 0), 'Ag', font=font)
            line_height = (line_box[3] - line_box[1]) + self.config.get('line_spacing', 6)
            total_height = len(lines) * line_height
            if total_height <= max_height:
                top_padding = self.config.get('top_padding', 4)
                y = y1 + top_padding
                for line in lines:
                    bbox = draw.textbbox((0, 0), line, font=font)
                    width = bbox[2] - bbox[0]
                    x = x1 + 4 if align == 'left' else x1 + (max_width - width) // 2
                    draw.text((x, y), line, fill='black', font=font)
                    y += line_height
                return
            size -= 1

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
        y = self.attitude['y']
        radius = self.attitude['radius']
        for i, x in enumerate(self.attitude['x_positions'], start=1):
            draw.ellipse((x - radius, y - radius, x + radius, y + radius), outline=cross_color, width=2)
            draw.text((x - 8, y + radius + 4), str(i), fill=cross_color, font=label_font)

    def generate_character(self, pools):
        character = {}
        for field_name, csv_column in self.field_mapping.items():
            if csv_column is None:
                character[field_name] = ''
            else:
                character[field_name] = pools[csv_column].draw()
        return character

    def render_sheet(self, character, rng):
        img = Image.open(self.template_path).convert('RGB')
        draw = ImageDraw.Draw(img)
        for field_name, layout in self.field_layouts.items():
            box = tuple(layout['box'])
            size = layout['font_size']
            align = layout.get('align', 'left')
            value = character.get(field_name, '').strip()
            if value:
                self.fit_and_draw(draw, box, value, size, align)
        idx = rng.randrange(len(self.attitude['x_positions']))
        cx = self.attitude['x_positions'][idx]
        cy = self.attitude['y']
        r = self.attitude['radius']
        line_width = self.attitude['line_width']
        draw.line((cx-r, cy-r, cx+r, cy+r), fill='black', width=line_width)
        draw.line((cx-r, cy+r, cx+r, cy-r), fill='black', width=line_width)
        self.draw_debug_overlay(draw)
        return img

    def compose_a4_pages(self, images, output_dir, base_name):
        margin = self.config['a4_layout']['margin']
        gap = self.config['a4_layout']['gap']
        columns = 2
        rows = 2
        cell_w = (self.a4[0] - margin * 2 - gap * (columns - 1)) // columns
        cell_h = (self.a4[1] - margin * 2 - gap * (rows - 1)) // rows
        positions = []
        for row in range(rows):
            for col in range(columns):
                x = margin + col * (cell_w + gap)
                y = margin + row * (cell_h + gap)
                positions.append((x, y))
        pages = []
        total_pages = math.ceil(len(images) / 4)
        for page_index in range(total_pages):
            page = Image.new('RGB', self.a4, 'white')
            chunk = images[page_index * 4:(page_index + 1) * 4]
            for img, (x, y) in zip(chunk, positions):
                copy = img.copy()
                copy.thumbnail((cell_w, cell_h), Image.LANCZOS)
                px = x + (cell_w - copy.width) // 2
                py = y + (cell_h - copy.height) // 2
                page.paste(copy, (px, py))
            page_stem = f'{base_name}_a4_page_{page_index + 1}'
            out_path = next_free_path(output_dir, page_stem, '.png')
            page.save(out_path)
            pages.append(out_path)
        return pages

    def generate_batch(self, count, seed, output_dir, base_name='charbogen'):
        rng = random.Random(seed)
        pools = self.build_pools(rng)
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        rendered = []
        single_files = []
        for i in range(1, count + 1):
            character = self.generate_character(pools)
            img = self.render_sheet(character, rng)
            single_stem = f'{base_name}_{i:03d}'
            single_path = next_free_path(output_dir, single_stem, '.png')
            img.save(single_path)
            single_files.append(single_path)
            rendered.append(img)
        a4_files = self.compose_a4_pages(rendered, output_dir, base_name)
        return single_files, a4_files

    def generate_preview(self, seed=None, pools=None):
        rng = random.Random(seed)
        if pools is None:
            pools = self.build_pools(rng)
        character = self.generate_character(pools)
        return self.render_sheet(character, rng)


class App(tk.Tk):
    def __init__(self, generator):
        super().__init__()
        self.generator = generator
        self.title('Charakterbogen Generator')
        self.geometry('1180x920')
        self.preview_photo = None
        self.current_preview_seed = None
        self.last_auto_seed = None
        self.preview_pools = None
        self._prev_pool_seed = None
        self.debug_enabled = bool(self.generator.config.get('debug', {}).get('enabled', False))
        self._build_ui()
        self.refresh_preview()

    def _build_ui(self):
        main = ttk.Frame(self, padding=12)
        main.pack(fill='both', expand=True)

        controls = ttk.Frame(main)
        controls.pack(fill='x', pady=(0, 10))

        ttk.Label(controls, text='Seed:').grid(row=0, column=0, sticky='w', padx=(0, 6))
        self.seed_var = tk.StringVar()
        ttk.Entry(controls, textvariable=self.seed_var, width=20).grid(row=0, column=1, sticky='w', padx=(0, 12))

        ttk.Button(controls, text='Aktualisieren', command=self.refresh_preview).grid(row=0, column=2, sticky='w', padx=(0, 12))

        ttk.Label(controls, text='Anzahl Bögen:').grid(row=0, column=3, sticky='w', padx=(12, 6))
        self.count_var = tk.StringVar(value='4')
        ttk.Entry(controls, textvariable=self.count_var, width=10).grid(row=0, column=4, sticky='w', padx=(0, 12))

        ttk.Button(controls, text='Generieren', command=self.generate_files).grid(row=0, column=5, sticky='w', padx=(0, 12))

        if self.debug_enabled:
            ttk.Button(controls, text='JSON neu einlesen', command=self.reload_config).grid(row=0, column=6, sticky='w')

        info_text = 'Vorschau zeigt immer einen zufällig erzeugten Bogen. Das Seed-Feld zeigt den aktuell angezeigten Vorschau-Seed und kann auch manuell gesetzt werden.'
        if self.debug_enabled:
            info_text += ' Debug-Modus aktiv: Feldrahmen und Marker werden eingeblendet.'
        info = ttk.Label(main, text=info_text)
        info.pack(fill='x', pady=(0, 10))

        preview_frame = ttk.LabelFrame(main, text='Vorschau', padding=10)
        preview_frame.pack(fill='both', expand=True)

        self.preview_label = ttk.Label(preview_frame)
        self.preview_label.pack(fill='both', expand=True)

        self.status_var = tk.StringVar(value='Bereit.')
        ttk.Label(main, textvariable=self.status_var).pack(fill='x', pady=(10, 0))

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
        try:
            seed, user_locked = self.determine_preview_seed()
            # Pool zurücksetzen wenn Seed manuell geändert wurde
            if self.preview_pools is None or seed != self._prev_pool_seed:
                self.preview_pools = self.generator.build_pools(random.Random(seed))
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
        try:
            config = load_config()
            self.generator.reload_from_config(config)
            self.debug_enabled = bool(self.generator.config.get('debug', {}).get('enabled', False))
            self.refresh_preview()
            self.status_var.set('config.json wurde neu eingelesen.')
        except Exception as e:
            messagebox.showerror('Fehler beim Neueinlesen', str(e))

    def generate_files(self):
        try:
            seed = self.parse_seed()
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
            single_files, a4_files = self.generator.generate_batch(count, seed, target_dir)
            self.status_var.set(f'Erstellt: {len(single_files)} Einzeldateien, {len(a4_files)} A4-Seiten in {target_dir}')
            messagebox.showinfo('Fertig', f'{len(single_files)} Bögen und {len(a4_files)} A4-Seiten wurden gespeichert.')
        except Exception as e:
            messagebox.showerror('Fehler', str(e))


def load_config():
    with open(CONFIG_PATH, 'r', encoding='utf-8') as f:
        return json.load(f)


def main():
    config = load_config()
    generator = CharacterGenerator(config)
    app = App(generator)
    app.mainloop()


if __name__ == '__main__':
    main()
