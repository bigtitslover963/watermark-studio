from pathlib import Path
import colorsys
import faulthandler
import filecmp
import gc
import json
import os
import queue
import re
import shutil
import sys
import threading
import traceback
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageFilter, ImageFont, ImageOps, ImageTk
import updater


ROOT = Path(__file__).resolve().parent
MARK = ROOT / "bigtitslover963.png"
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}
MAX_PIXELS = 40_000_000
ORIGINAL_PURPLE = "#7920ad"
FONT_EXTENSIONS = {".ttf", ".otf", ".ttc"}
POSITIONS = ("Top left", "Top center", "Top right", "Middle left", "Center",
             "Middle right", "Bottom left", "Bottom center", "Bottom right")


def preset_path():
    return imported_font_dir().parent / "presets.json"


def read_presets(path=None):
    path = Path(path) if path else preset_path()
    if not path.exists():
        return {}
    with path.open(encoding="utf-8") as stream:
        data = json.load(stream)
    if not isinstance(data, dict):
        raise ValueError("Saved presets file is invalid.")
    return data


def write_presets(presets, path=None):
    path = Path(path) if path else preset_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_name(path.name + ".tmp")
    try:
        with temporary.open("w", encoding="utf-8") as stream:
            json.dump(presets, stream, ensure_ascii=False, indent=2)
        os.replace(temporary, path)
    finally:
        temporary.unlink(missing_ok=True)


def placement(canvas_size, overlay_size, choice, margin):
    if choice not in POSITIONS:
        raise ValueError("Choose a valid watermark position.")
    across = choice.split()[-1]
    down = choice.split()[0]
    width, height = canvas_size
    mark_width, mark_height = overlay_size
    x = margin if across == "left" else width - margin - mark_width if across == "right" else (width - mark_width) // 2
    y = margin if down == "Top" else height - margin - mark_height if down == "Bottom" else (height - mark_height) // 2
    return max(0, x), max(0, y)


def set_opacity(mark, percent):
    if not 0 <= percent <= 100:
        raise ValueError("Choose opacity between 0% and 100%.")
    if percent == 100:
        return mark
    result = mark.copy()
    result.putalpha(mark.getchannel("A").point(lambda alpha: round(alpha * percent / 100)))
    return result


def imported_font_dir():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "WatermarkStudio" / "fonts"


def font_label(path, imported=False):
    family, style = ImageFont.truetype(str(path), 24).getname()
    name = f"{family} ({style})" if style.lower() != "regular" else family
    return f"{name} [Imported: {path.name}]" if imported else name


def import_font(source, destination_dir=None):
    source = Path(source)
    if source.suffix.lower() not in FONT_EXTENSIONS or source.stat().st_size > 20 * 1024 * 1024:
        raise ValueError("Choose a TTF, OTF, or TTC font under 20 MB.")
    font_label(source)  # Validate the font before saving a copy.
    destination_dir = Path(destination_dir) if destination_dir else imported_font_dir()
    destination_dir.mkdir(parents=True, exist_ok=True)
    destination = destination_dir / source.name
    number = 2
    while destination.exists() and not filecmp.cmp(source, destination, shallow=False):
        destination = destination_dir / f"{source.stem} ({number}){source.suffix}"
        number += 1
    if not destination.exists():
        temporary = destination.with_name(destination.name + ".tmp")
        try:
            shutil.copyfile(source, temporary)
            os.replace(temporary, destination)
        finally:
            temporary.unlink(missing_ok=True)
    return font_label(destination, imported=True), str(destination)


def available_fonts():
    """Map readable font names to files Pillow can load on this computer."""
    roots = [Path(os.environ.get("WINDIR", r"C:\Windows")) / "Fonts"] if os.name == "nt" else [Path("/usr/share/fonts/truetype")]
    roots.append(imported_font_dir())
    found = {}
    for root in roots:
        if not root.exists():
            continue
        for path in sorted(root.rglob("*")):
            if path.suffix.lower() not in FONT_EXTENSIONS:
                continue
            try:
                label = font_label(path, imported=root == roots[-1])
            except (OSError, ValueError):
                continue
            found.setdefault(label, str(path))
    if not found:
        found["Default"] = "DejaVuSans.ttf"
    return dict(sorted(found.items(), key=lambda item: item[0].casefold()))


def make_watermark(text="", font_path=None, color=None, use_original_logo=False):
    text = text.strip()
    if use_original_logo:
        with Image.open(MARK) as graphic:
            watermark = graphic.convert("RGBA")
            bounds = watermark.getbbox()
            if bounds is None:
                raise ValueError("The watermark graphic is empty.")
            return colored_watermark(watermark.crop(bounds), color)
    if not text:
        raise ValueError("Enter watermark text or select Use original logo.")
    if len(text) > 120 or any(ord(ch) < 32 for ch in text):
        raise ValueError("Use one line of watermark text, up to 120 characters.")
    font = ImageFont.truetype(font_path or "DejaVuSans.ttf", 128)
    bounds = font.getbbox(text)
    mark = Image.new("RGBA", (max(1, bounds[2] - bounds[0]) + 8,
                              max(1, bounds[3] - bounds[1]) + 8), (0, 0, 0, 0))
    ImageDraw.Draw(mark).text((4 - bounds[0], 4 - bounds[1]), text, font=font,
                              fill=color or ORIGINAL_PURPLE)
    return mark


def crash_log_path():
    return Path(os.environ.get("LOCALAPPDATA", str(Path.home()))) / "WatermarkStudio" / "crash.log"


def record_error(context, exc):
    try:
        path = crash_log_path()
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as log:
            log.write(f"\n{context}\n")
            traceback.print_exception(type(exc), exc, exc.__traceback__, file=log)
    except OSError:
        pass


def watermark_one(source, output_temp, watermark, width_percent, position="Bottom left", opacity=100):
    with Image.open(source) as raw:
        if raw.width * raw.height > MAX_PIXELS:
            raise ValueError("Image exceeds 40 megapixels; reduce its dimensions before processing.")
        original = ImageOps.exif_transpose(raw)
        try:
            suffix = source.suffix.lower()
            mode = "RGBA" if suffix in {".png", ".webp"} else "RGB"
            canvas = original.convert(mode)
            try:
                target_width = max(1, round(canvas.width * width_percent / 100))
                margin = max(1, round(min(canvas.size) * 0.02))
                scale = min(target_width / watermark.width,
                            max(1, canvas.width - 2 * margin) / watermark.width,
                            max(1, canvas.height - 2 * margin) / watermark.height)
                size = (max(1, round(watermark.width * scale)),
                        max(1, round(watermark.height * scale)))
                with watermark.resize(size, Image.Resampling.LANCZOS) as overlay:
                    point = placement(canvas.size, size, position, margin)
                    faded = set_opacity(overlay, opacity)
                    if mode == "RGBA":
                        canvas.alpha_composite(faded, point)
                    else:
                        canvas.paste(faded, point, faded.getchannel("A"))
                    if faded is not overlay:
                        faded.close()
                if suffix in {".jpg", ".jpeg"}:
                    canvas.save(output_temp, format="JPEG", quality=95, subsampling=0)
                elif suffix == ".webp":
                    canvas.save(output_temp, format="WEBP", quality=95)
                else:
                    canvas.save(output_temp, format="PNG")
            finally:
                canvas.close()
        finally:
            if original is not raw:
                original.close()


def colored_watermark(watermark: Image.Image, color: str | None) -> Image.Image:
    if color is None:
        return watermark
    rgb = tuple(bytes.fromhex(color.lstrip("#")))
    if len(rgb) != 3:
        raise ValueError("Choose a valid watermark color.")
    result = Image.new("RGBA", watermark.size, rgb + (0,))
    result.putalpha(watermark.getchannel("A"))
    return result


def process_folder(folder: Path, width_percent: int = 25, color: str | None = None,
                   replace_existing: bool = False, character_name: str = "",
                   watermark_text: str = "", font_path: str | None = None,
                   position: str = "Bottom left", opacity: int = 100,
                   use_original_logo: bool = False):
    if not folder.is_dir():
        raise ValueError("Choose a folder containing images.")
    if use_original_logo and not MARK.is_file():
        raise FileNotFoundError(f"Watermark graphic is missing: {MARK}")
    if position not in POSITIONS or not 0 <= opacity <= 100:
        raise ValueError("Choose a valid watermark position and opacity.")
    character_name = character_name.strip()
    if character_name and (len(character_name) > 140 or any(ch in character_name for ch in '<>:"/\\|?*')
                           or character_name.endswith((" ", ".")) or any(ord(ch) < 32 for ch in character_name)
                           or character_name.upper() in {"CON", "PRN", "AUX", "NUL"}):
        raise ValueError("The character name contains a character Windows cannot use in a filename.")
    destination = folder / "Watermarked"
    clean_destination = folder / "Named Originals" if character_name else None

    def natural_key(path):
        return [int(part) if part.isdigit() else part.casefold()
                for part in re.split(r"(\d+)", path.name)]

    files = [p for p in sorted(folder.iterdir(), key=natural_key)
             if p.is_file() and p.suffix.lower() in EXTENSIONS]
    if not files:
        raise ValueError("No PNG, JPG, JPEG, or WebP images found in that folder.")
    destination.mkdir(exist_ok=True)
    if clean_destination:
        clean_destination.mkdir(exist_ok=True)
    created, skipped, errors = 0, 0, []
    with make_watermark(watermark_text, font_path, color, use_original_logo) as watermark:
        for index, source in enumerate(files, start=1):
            clean = clean_destination / f"{character_name} {index}{source.suffix}" if clean_destination else None
            output = destination / (f"{character_name} {index}b{source.suffix}" if character_name
                                    else f"{source.stem}_watermarked{source.suffix}")
            if clean and not clean.exists():
                clean_temp = clean.with_name(clean.stem + ".tmp" + clean.suffix)
                try:
                    shutil.copy2(source, clean_temp)
                    os.replace(clean_temp, clean)
                except Exception as exc:
                    clean_temp.unlink(missing_ok=True)
                    errors.append(f"{source.name} (clean copy): {exc}")
                    continue
            if output.exists() and not replace_existing:
                skipped += 1
                continue
            output_temp = output.with_name(output.stem + ".tmp" + output.suffix)
            try:
                try:
                    with crash_log_path().open("a", encoding="utf-8") as log:
                        log.write(f"Processing {source}\n")
                except OSError:
                    pass
                watermark_one(source, output_temp, watermark, width_percent, position, opacity)
                os.replace(output_temp, output)
                created += 1
            except Exception as exc:
                record_error(f"Processing {source}", exc)
                errors.append(f"{source.name}: {exc}")
                output_temp.unlink(missing_ok=True)
            finally:
                gc.collect()
    return destination, created, skipped, errors


def main():
    window = tk.Tk()
    def report_callback_exception(exc_type, exc, tb):
        try:
            record_error("Interface callback", exc)
        finally:
            messagebox.showerror("Watermark Studio error", f"{exc}\n\nDetails: {crash_log_path()}", parent=window)
    window.report_callback_exception = report_callback_exception
    window.title("Watermark Studio")
    try:
        window.iconbitmap(str(ROOT / "WatermarkStudio.ico"))
    except tk.TclError:
        pass
    window.geometry("820x760")
    window.minsize(820, 540)
    BG, CARD, FIELD, FG, MUTED, ACCENT = "#090c19", "#10172b", "#172139", "#f0eaff", "#9a9bbb", "#a854ff"
    window.configure(bg=BG)
    style = ttk.Style(window)
    style.theme_use("clam")
    style.configure("Dark.TEntry", fieldbackground=FIELD, foreground=FG, bordercolor="#513778", padding=8)
    style.configure("Dark.TSpinbox", fieldbackground=FIELD, foreground=FG, arrowsize=13, padding=5)
    style.configure("Dark.TCombobox", fieldbackground=FIELD, background=FIELD, foreground=FG,
                    arrowcolor=ACCENT, bordercolor="#513778", padding=6)
    style.configure("Dark.TCheckbutton", background=CARD, foreground=FG, font=("Segoe UI", 10))
    style.map("Dark.TCheckbutton", background=[("active", CARD)], foreground=[("active", FG)])

    def label(parent, text, size=10, color=FG, bold=False):
        return tk.Label(parent, text=text, bg=parent.cget("bg"), fg=color,
                        font=("Segoe UI", size, "bold" if bold else "normal"), anchor="w")

    def button(parent, text, command, primary=False):
        normal = ACCENT if primary else FIELD
        hover = "#c381ff" if primary else "#30234d"
        widget = tk.Button(parent, text=text, command=command, bg=normal, fg="#ffffff",
                           activebackground=hover, activeforeground="#ffffff", bd=0,
                           font=("Segoe UI", 10, "bold"), padx=15, pady=9, cursor="hand2")
        widget.bind("<Enter>", lambda e: widget.configure(bg=hover))
        widget.bind("<Leave>", lambda e: widget.configure(bg=normal))
        return widget

    def neon_card(parent, padding=(17, 12), pady=(0, 15)):
        glow = tk.Frame(parent, bg="#39245b", padx=2, pady=2)
        glow.pack(fill="x", padx=30, pady=pady)
        outline = tk.Frame(glow, bg="#8750c7", padx=1, pady=1)
        outline.pack(fill="x")
        inner = tk.Frame(outline, bg=CARD, padx=padding[0], pady=padding[1])
        inner.pack(fill="x")
        return inner

    # Keep the main action in a fixed footer; scroll the settings when display
    # scaling or a smaller screen makes the content taller than the window.
    footer = tk.Frame(window, bg=BG, padx=30, pady=14)
    footer.pack(side="bottom", fill="x")
    scroll_area = tk.Frame(window, bg=BG)
    scroll_area.pack(side="top", fill="both", expand=True)
    scroll = tk.Canvas(scroll_area, bg=BG, highlightthickness=0, bd=0)
    bar = tk.Scrollbar(scroll_area, orient="vertical", command=scroll.yview,
                       bg="#362158", troughcolor=BG, activebackground=ACCENT)
    bar.pack(side="right", fill="y")
    scroll.pack(side="left", fill="both", expand=True)
    scroll.configure(yscrollcommand=bar.set)
    content = tk.Frame(scroll, bg=BG)
    content_id = scroll.create_window((0, 0), window=content, anchor="nw")
    content.bind("<Configure>", lambda event: scroll.configure(scrollregion=scroll.bbox("all")))
    scroll.bind("<Configure>", lambda event: scroll.itemconfigure(content_id, width=event.width))

    def on_wheel(event):
        if window.focus_get() is not None and window.focus_get().winfo_toplevel() == window:
            scroll.yview_scroll(-int(event.delta / 120), "units")

    window.bind_all("<MouseWheel>", on_wheel)

    header = tk.Frame(content, bg=BG, padx=30, pady=18)
    header.pack(fill="x")
    label(header, "Watermark Studio", 25, FG, True).pack(anchor="w")
    label(header, "BATCH PROCESSING  /  CUSTOM COLOR  /  NUMBERED PAIRS", 9, MUTED).pack(anchor="w")
    rail = tk.Canvas(content, width=760, height=9, bg=BG, bd=0, highlightthickness=0)
    rail.pack(pady=(0, 15))
    for width, color in ((8, "#1c1235"), (4, "#4b2a7c"), (2, ACCENT)):
        rail.create_line(4, 4, 756, 4, fill=color, width=width)

    preview_card = neon_card(content)
    label(preview_card, "◈  LIVE PREVIEW", 10, ACCENT, True).pack(anchor="w", pady=(0, 8))
    preview_label = tk.Label(preview_card, bg="#111930", bd=0)
    preview_label.pack()

    controls = neon_card(content, padding=(18, 14), pady=(0, 15))
    label(controls, "01  /  IMAGE FOLDER", 10, ACCENT, True).pack(anchor="w", pady=(0, 7))
    folder_var = tk.StringVar(value=sys.argv[1] if len(sys.argv) > 1 else "")
    row = tk.Frame(controls, bg=CARD)
    row.pack(fill="x")
    ttk.Entry(row, textvariable=folder_var, style="Dark.TEntry").pack(side="left", fill="x", expand=True)
    button(row, "Browse", command=lambda: folder_var.set(
        filedialog.askdirectory(title="Choose your original images folder") or folder_var.get()
    )).pack(side="left", padx=(10, 0))

    label(controls, "02  /  CHARACTER NAME (OPTIONAL)", 10, ACCENT, True).pack(anchor="w", pady=(16, 6))
    character_var = tk.StringVar()
    ttk.Entry(controls, textvariable=character_var, style="Dark.TEntry").pack(fill="x")
    label(controls, "Example: Rias Gremory 1.png  +  Rias Gremory 1b.png", 9, MUTED).pack(anchor="w", pady=(5, 0))

    label(controls, "03  /  WATERMARK TEXT", 10, ACCENT, True).pack(anchor="w", pady=(16, 6))
    watermark_text_var = tk.StringVar()
    ttk.Entry(controls, textvariable=watermark_text_var, style="Dark.TEntry").pack(fill="x")
    use_original_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(controls, text="Use original BIGTITSLOVER963 logo instead of text",
                    variable=use_original_var).pack(anchor="w", pady=(7, 0))
    fonts = available_fonts()
    default_font = next((name for name in fonts if name.casefold() == "segoe ui"), next(iter(fonts)))
    font_var = tk.StringVar(value=default_font)
    label(controls, "FONT FOR CUSTOM TEXT", 9, MUTED, True).pack(anchor="w", pady=(12, 5))
    font_row = tk.Frame(controls, bg=CARD)
    font_row.pack(fill="x")
    font_picker = ttk.Combobox(font_row, textvariable=font_var, values=list(fonts), state="readonly",
                               style="Dark.TCombobox")
    font_picker.pack(side="left", fill="x", expand=True)

    def choose_font():
        source = filedialog.askopenfilename(title="Import a font", parent=window,
                                            filetypes=[("Font files", "*.ttf *.otf *.ttc")])
        if not source:
            return
        try:
            name, path = import_font(source)
        except (OSError, ValueError) as exc:
            messagebox.showerror("Could not import font", str(exc), parent=window)
            return
        fonts[name] = path
        font_picker.configure(values=sorted(fonts, key=str.casefold))
        font_var.set(name)

    button(font_row, "Import font", choose_font).pack(side="left", padx=(10, 0))

    settings = tk.Frame(controls, bg=CARD)
    settings.pack(fill="x", pady=(18, 0))
    left = tk.Frame(settings, bg=CARD)
    left.pack(side="left", anchor="n", fill="x", expand=True, padx=(0, 24))
    right = tk.Frame(settings, bg=CARD)
    right.pack(side="left", anchor="n", fill="x", expand=True)
    label(left, "04  /  WATERMARK SIZE", 10, ACCENT, True).pack(anchor="w")
    label(left, "Width as a percent of the image", 9, MUTED).pack(anchor="w", pady=(1, 5))
    width_var = tk.IntVar(value=25)
    ttk.Spinbox(left, from_=5, to=60, textvariable=width_var, width=7,
                style="Dark.TSpinbox").pack(anchor="w")
    label(right, "05  /  LETTERING COLOR", 10, ACCENT, True).pack(anchor="w")
    color_var = tk.StringVar(value="Original purple")
    selected_color = [None]
    color_row = tk.Frame(right, bg=CARD)
    color_row.pack(fill="x", pady=(7, 0))
    hue_var = tk.IntVar(value=278)
    swatch = tk.Label(color_row, width=3, bg="#7920ad", relief="solid", bd=1,
                      highlightbackground=ACCENT, highlightthickness=2)
    position_var = tk.StringVar(value="Bottom left")
    opacity_var = tk.IntVar(value=100)

    def update_preview(*_):
        backdrop = Image.new("RGBA", (700, 150), "#0d1529")
        glow = Image.new("RGBA", backdrop.size)
        brush = ImageDraw.Draw(glow)
        brush.ellipse((185, -76, 540, 206), fill=(140, 55, 240, 105))
        backdrop = Image.alpha_composite(backdrop, glow.filter(ImageFilter.GaussianBlur(54)))
        brush = ImageDraw.Draw(backdrop)
        for x in range(0, 700, 25):
            brush.line((x, 0, x, 150), fill=(112, 72, 170, 22))
        for y in range(0, 150, 25):
            brush.line((0, y, 700, y), fill=(112, 72, 170, 22))
        brush.rectangle((0, 0, 699, 149), outline=(149, 75, 237, 180), width=1)
        if not use_original_var.get() and not watermark_text_var.get().strip():
            brush.text((16, 123), "Enter watermark text to preview", fill="#aa9bbd")
            photo = ImageTk.PhotoImage(backdrop)
            preview_label.configure(image=photo)
            preview_label.image = photo
            return
        try:
            mark = make_watermark(watermark_text_var.get(), fonts[font_var.get()],
                                  selected_color[0], use_original_var.get())
        except (OSError, ValueError):
            return
        try:
            width = min(60, max(5, width_var.get()))
        except tk.TclError:
            width = 25
        size = (max(1, round(700 * width / 100)), 0)
        size = (size[0], max(1, round(size[0] * mark.height / mark.width)))
        if size[1] > 120:
            size = (max(1, round(size[0] * 120 / size[1])), 120)
        with mark.resize(size, Image.Resampling.LANCZOS) as overlay:
            faded = set_opacity(overlay, opacity_var.get())
            backdrop.alpha_composite(faded, placement(backdrop.size, size, position_var.get(), 14))
            if faded is not overlay:
                faded.close()
        mark.close()
        photo = ImageTk.PhotoImage(backdrop)
        preview_label.configure(image=photo)
        preview_label.image = photo

    def set_color(color):
        selected_color[0] = color
        color_var.set(color or "Original purple")
        swatch.configure(bg=color or "#7920ad")
        update_preview()

    def change_hue(value):
        rgb = colorsys.hsv_to_rgb(float(value) / 360, 0.85, 0.8)
        set_color("#" + "".join(f"{round(channel * 255):02x}" for channel in rgb))

    tk.Scale(color_row, from_=0, to=359, orient="horizontal", variable=hue_var,
             command=change_hue, showvalue=False, length=172, bg=CARD, fg=FG,
             troughcolor="#2c1a4b", activebackground=ACCENT, highlightthickness=0,
             bd=0).pack(side="left")
    swatch.pack(side="left", padx=8)
    tk.Label(right, textvariable=color_var, bg=CARD, fg=FG,
             font=("Segoe UI", 9)).pack(anchor="w", pady=(4, 0))

    def pick_color():
        _, choice = colorchooser.askcolor(color=selected_color[0] or "#7920ad", parent=window)
        if choice:
            set_color(choice)

    buttons = tk.Frame(right, bg=CARD)
    buttons.pack(anchor="w", pady=(5, 0))
    button(buttons, "Pick color", pick_color).pack(side="left")
    button(buttons, "Original purple", lambda: set_color(None)).pack(side="left", padx=7)

    more_settings = tk.Frame(controls, bg=CARD)
    more_settings.pack(fill="x", pady=(17, 0))
    position_box = tk.Frame(more_settings, bg=CARD)
    position_box.pack(side="left", fill="x", expand=True, padx=(0, 20))
    label(position_box, "06  /  POSITION", 10, ACCENT, True).pack(anchor="w", pady=(0, 5))
    ttk.Combobox(position_box, textvariable=position_var, values=POSITIONS, state="readonly",
                 style="Dark.TCombobox").pack(fill="x")
    opacity_box = tk.Frame(more_settings, bg=CARD)
    opacity_box.pack(side="left", fill="x", expand=True)
    opacity_heading = tk.Frame(opacity_box, bg=CARD)
    opacity_heading.pack(fill="x")
    label(opacity_heading, "07  /  OPACITY", 10, ACCENT, True).pack(side="left")
    tk.Label(opacity_heading, textvariable=opacity_var, bg=CARD, fg=FG,
             font=("Segoe UI", 10)).pack(side="right")
    tk.Scale(opacity_box, from_=0, to=100, orient="horizontal", variable=opacity_var,
             showvalue=False, bg=CARD, fg=FG, troughcolor="#2c1a4b", activebackground=ACCENT,
             highlightthickness=0, bd=0, command=lambda _: update_preview()).pack(fill="x")

    label(controls, "08  /  SAVED PRESETS", 10, ACCENT, True).pack(anchor="w", pady=(18, 7))
    preset_row = tk.Frame(controls, bg=CARD)
    preset_row.pack(fill="x")
    preset_var = tk.StringVar()
    preset_box = ttk.Combobox(preset_row, textvariable=preset_var, style="Dark.TCombobox")
    preset_box.pack(side="left", fill="x", expand=True)

    def refresh_presets():
        preset_box.configure(values=sorted(read_presets(), key=str.casefold))

    def save_preset():
        name = preset_var.get().strip()
        if not name or len(name) > 50:
            messagebox.showerror("Preset name", "Enter a preset name of up to 50 characters.", parent=window)
            return
        try:
            presets = read_presets()
            if name in presets and not messagebox.askyesno("Replace preset", f"Replace '{name}'?", parent=window):
                return
            presets[name] = {"text": watermark_text_var.get(), "font": font_var.get(),
                             "use_original_logo": use_original_var.get(),
                             "color": selected_color[0], "width": width_var.get(),
                             "position": position_var.get(), "opacity": opacity_var.get()}
            write_presets(presets)
            refresh_presets()
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            messagebox.showerror("Could not save preset", str(exc), parent=window)

    def load_preset():
        try:
            presets = read_presets()
            name = preset_var.get().strip()
            if name not in presets:
                messagebox.showinfo("Load preset", "Choose a saved preset first.", parent=window)
                return
            settings = presets[name]
            if settings["font"] not in fonts:
                raise ValueError("This preset's font is missing. Import that font again to use it.")
            color = settings["color"]
            if color is not None and not re.fullmatch(r"#[0-9a-fA-F]{6}", color):
                raise ValueError("The preset color is invalid.")
            width, opacity = int(settings["width"]), int(settings["opacity"])
            if not 5 <= width <= 60 or not 0 <= opacity <= 100 or settings["position"] not in POSITIONS:
                raise ValueError("The preset contains invalid settings.")
            watermark_text_var.set(settings["text"])
            use_original_var.set(settings.get("use_original_logo", not settings["text"].strip()))
            font_var.set(settings["font"])
            width_var.set(width)
            position_var.set(settings["position"])
            opacity_var.set(opacity)
            set_color(color)
        except (OSError, ValueError, TypeError, KeyError, json.JSONDecodeError) as exc:
            messagebox.showerror("Could not load preset", str(exc), parent=window)

    def delete_preset():
        name = preset_var.get().strip()
        try:
            presets = read_presets()
            if name not in presets:
                messagebox.showinfo("Delete preset", "Choose a saved preset first.", parent=window)
                return
            if not messagebox.askyesno("Delete preset", f"Delete '{name}'?", parent=window):
                return
            del presets[name]
            write_presets(presets)
            preset_var.set("")
            refresh_presets()
        except (OSError, ValueError, json.JSONDecodeError) as exc:
            messagebox.showerror("Could not delete preset", str(exc), parent=window)

    button(preset_row, "Save", save_preset).pack(side="left", padx=(8, 0))
    button(preset_row, "Load", load_preset).pack(side="left", padx=(6, 0))
    button(preset_row, "Delete", delete_preset).pack(side="left", padx=(6, 0))
    try:
        refresh_presets()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        messagebox.showerror("Could not read presets", str(exc), parent=window)
    replace_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(controls, text="Replace existing watermarked copies", variable=replace_var,
                    style="Dark.TCheckbutton").pack(anchor="w", pady=(14, 0))
    status = tk.StringVar(value="New copies go into a Watermarked folder. Existing copies are skipped.")
    tk.Label(footer, textvariable=status, bg=BG, fg=MUTED, anchor="w",
             font=("Segoe UI", 9)).pack(anchor="w", pady=(0, 11))

    def show_result(destination, created, skipped, errors, named=False):
        popup = tk.Toplevel(window)
        popup.title("Batch finished | Watermark Studio")
        popup.configure(bg=BG)
        popup.resizable(False, False)
        popup.transient(window)
        height = (440 if errors else 380) if named else (400 if errors else 335)
        window.update_idletasks()
        x = window.winfo_rootx() + (window.winfo_width() - 510) // 2
        y = window.winfo_rooty() + (window.winfo_height() - height) // 2
        popup.geometry(f"510x{height}+{x}+{y}")

        body = tk.Frame(popup, bg=BG, padx=27, pady=22)
        body.pack(fill="both", expand=True)
        label(body, "◈  BATCH FINISHED", 18, ACCENT, True).pack(anchor="w")
        label(body, "Your originals are untouched.", 10, MUTED).pack(anchor="w", pady=(2, 17))

        stats = tk.Frame(body, bg=BG)
        stats.pack(fill="x")
        for title, count, color in (("CREATED", created, "#b475fa"),
                                     ("SKIPPED", skipped, "#c3b7d9"),
                                     ("FAILED", len(errors), "#ff8b9b")):
            card = tk.Frame(stats, bg=CARD, padx=14, pady=12,
                            highlightbackground="#6c3caa", highlightthickness=1)
            card.pack(side="left", fill="x", expand=True, padx=(0, 8))
            label(card, str(count), 23, color, True).pack(anchor="w")
            label(card, title, 9, MUTED, True).pack(anchor="w")

        label(body, "SAVED IN", 9, MUTED, True).pack(anchor="w", pady=(18, 3))
        path_field = tk.Entry(body, bg=FIELD, fg=FG, readonlybackground=FIELD,
                              relief="flat", font=("Segoe UI", 9))
        path_field.insert(0, str(destination))
        path_field.configure(state="readonly")
        path_field.pack(fill="x", ipady=7)
        if errors:
            details = label(body, "Failed files: " + "; ".join(errors[:3]), 9, "#ff8b9b")
            details.configure(wraplength=450, justify="left")
            details.pack(anchor="w", pady=(9, 0))

        actions = tk.Frame(body, bg=BG)
        actions.pack(anchor="w", pady=(17, 0))

        def open_folder():
            try:
                os.startfile(destination)
            except OSError as exc:
                messagebox.showerror("Could not open folder", str(exc), parent=popup)

        button(actions, "OPEN WATERMARKED FOLDER", open_folder, True).pack(side="left")
        button(actions, "Close", popup.destroy).pack(side="left", padx=(9, 0))
        if named:
            button(body, "OPEN NAMED ORIGINALS", lambda: os.startfile(destination.parent / "Named Originals")).pack(
                anchor="w", pady=(8, 0))
        popup.bind("<Escape>", lambda event: popup.destroy())
        popup.grab_set()
        popup.focus_set()

    def run():
        status.set("Processing images...")
        window.update_idletasks()
        try:
            width = width_var.get()
            if not 5 <= width <= 60:
                raise ValueError("Choose a watermark width between 5% and 60%.")
            destination, created, skipped, errors = process_folder(
                Path(folder_var.get()), width, selected_color[0], replace_var.get(), character_var.get(),
                watermark_text_var.get(), fonts[font_var.get()], position_var.get(), opacity_var.get(),
                use_original_var.get())
        except Exception as exc:
            record_error("Creating watermarked copies", exc)
            messagebox.showerror("Watermark Tool", str(exc))
            return
        status.set(f"Created {created}; skipped {skipped}; failed {len(errors)}.")
        show_result(destination, created, skipped, errors, bool(character_var.get().strip()))

    button(footer, "CREATE WATERMARKED COPIES", run, True).pack(anchor="w")
    update_queue = queue.Queue()

    def check_updates(manual=False):
        if not getattr(sys, "frozen", False) or not updater.build_info().get("repository"):
            if manual:
                messagebox.showinfo("Updates", "Automatic updates become available in the GitHub release build.", parent=window)
            return

        def worker():
            try:
                update_queue.put(("checked", updater.latest_release(), manual))
            except Exception as exc:
                update_queue.put(("error", str(exc), manual))

        threading.Thread(target=worker, daemon=True).start()

    def poll_updates():
        while not update_queue.empty():
            kind, value, manual = update_queue.get_nowait()
            if kind == "error":
                if manual:
                    messagebox.showerror("Update check failed", value, parent=window)
            elif kind == "checked":
                if value is None:
                    if manual:
                        messagebox.showinfo("Updates", "You have the latest version.", parent=window)
                else:
                    version, exe_url, digest_url = value
                    if messagebox.askyesno("Update available", f"Version {version} is ready. Download and install it now?", parent=window):
                        status.set("Downloading update and checking its SHA256 checksum...")

                        def download():
                            try:
                                update_queue.put(("downloaded", updater.download_update(exe_url, digest_url), True))
                            except Exception as exc:
                                update_queue.put(("error", str(exc), True))

                        threading.Thread(target=download, daemon=True).start()
            elif kind == "downloaded":
                try:
                    updater.install_after_exit(value)
                    window.destroy()
                    return
                except Exception as exc:
                    messagebox.showerror("Installation failed", str(exc), parent=window)
        window.after(250, poll_updates)

    button(footer, "CHECK FOR UPDATES", lambda: check_updates(True)).pack(anchor="w", pady=(7, 0))
    label(footer, "Original images stay untouched", 9, MUTED).pack(anchor="w", pady=(9, 0))
    width_var.trace_add("write", update_preview)
    watermark_text_var.trace_add("write", update_preview)
    use_original_var.trace_add("write", update_preview)
    font_var.trace_add("write", update_preview)
    position_var.trace_add("write", update_preview)
    opacity_var.trace_add("write", update_preview)
    window.after(0, update_preview)
    window.after(250, poll_updates)
    window.after(4000, check_updates)
    window.mainloop()


if __name__ == "__main__":
    if "--self-test" in sys.argv:
        import tempfile
        with tempfile.TemporaryDirectory() as directory:
            sample = Path(directory)
            Image.new("RGB", (640, 480), "#453370").save(sample / "sample.jpg")
            Image.new("RGBA", (640, 480), "#453370").save(sample / "sample.png")
            try:
                make_watermark()
            except ValueError:
                pass
            else:
                raise RuntimeError("Blank watermark text unexpectedly selected a logo")
            _, created, _, errors = process_folder(sample, 25, character_name="Example",
                                                    use_original_logo=True)
            if created != 2 or errors:
                raise RuntimeError(f"Watermark processing self-test failed: {errors}")
            font_path = next(iter(available_fonts().values()))
            if Path(font_path).is_file():
                with tempfile.TemporaryDirectory() as font_directory:
                    imported_name, imported_path = import_font(font_path, font_directory)
                    if "[Imported:" not in imported_name or not Path(imported_path).is_file():
                        raise RuntimeError("Import font self-test failed")
                    with make_watermark("Imported font", imported_path) as imported_mark:
                        if imported_mark.getbbox() is None:
                            raise RuntimeError("Imported font rendering failed")
            _, created, _, errors = process_folder(sample, 25, color="#aa55ff",
                                                   character_name="Custom", watermark_text="My Studio",
                                                   font_path=font_path, position="Top right", opacity=40)
            if created != 2 or errors:
                raise RuntimeError(f"Custom text self-test failed: {errors}")
            if placement((640, 480), (100, 30), "Top right", 10) != (530, 10):
                raise RuntimeError("Watermark position self-test failed")
            with Image.new("RGBA", (2, 2), (150, 80, 200, 255)) as solid:
                with set_opacity(solid, 40) as faded:
                    if faded.getchannel("A").getpixel((0, 0)) != 102:
                        raise RuntimeError("Watermark opacity self-test failed")
            settings_path = sample / "presets.json"
            write_presets({"Purple": {"width": 25, "opacity": 40}}, settings_path)
            if read_presets(settings_path)["Purple"]["opacity"] != 40:
                raise RuntimeError("Saved presets self-test failed")
    else:
        try:
            diagnostic = crash_log_path()
            diagnostic.parent.mkdir(parents=True, exist_ok=True)
            with diagnostic.open("a", encoding="utf-8") as log:
                faulthandler.enable(file=log)
                main()
        except Exception as exc:
            record_error("Application stopped", exc)
            try:
                emergency = tk.Tk()
                emergency.withdraw()
                messagebox.showerror("Watermark Studio stopped", f"{exc}\n\nCrash report: {crash_log_path()}")
                emergency.destroy()
            except Exception:
                pass
