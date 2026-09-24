from pathlib import Path
import colorsys
import os
import queue
import re
import shutil
import sys
import threading
import tkinter as tk
from tkinter import colorchooser, filedialog, messagebox, ttk

from PIL import Image, ImageDraw, ImageFilter, ImageOps, ImageTk
import updater


ROOT = Path(__file__).resolve().parent
MARK = ROOT / "bigtitslover963.png"
EXTENSIONS = {".png", ".jpg", ".jpeg", ".webp"}


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
                   replace_existing: bool = False, character_name: str = ""):
    if not folder.is_dir():
        raise ValueError("Choose a folder containing images.")
    if not MARK.is_file():
        raise FileNotFoundError(f"Watermark graphic is missing: {MARK}")
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
    with Image.open(MARK) as graphic:
        watermark = graphic.convert("RGBA")
        bounds = watermark.getbbox()
        if bounds is None:
            raise ValueError("The watermark graphic is empty.")
        watermark = colored_watermark(watermark.crop(bounds), color)
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
                with Image.open(source) as raw:
                    original = ImageOps.exif_transpose(raw)
                    canvas = original.convert("RGBA")
                    target_width = max(1, round(canvas.width * width_percent / 100))
                    margin = max(1, round(min(canvas.size) * 0.02))
                    max_width = max(1, canvas.width - 2 * margin)
                    max_height = max(1, canvas.height - 2 * margin)
                    scale = min(target_width / watermark.width, max_width / watermark.width,
                                max_height / watermark.height)
                    size = (max(1, round(watermark.width * scale)),
                            max(1, round(watermark.height * scale)))
                    overlay = watermark.resize(size, Image.Resampling.LANCZOS)
                    canvas.alpha_composite(overlay, (margin, canvas.height - margin - size[1]))
                    suffix = source.suffix.lower()
                    if suffix in {".jpg", ".jpeg"}:
                        rgb = Image.new("RGB", canvas.size, "white")
                        rgb.paste(canvas, mask=canvas.getchannel("A"))
                        rgb.save(output_temp, format="JPEG", quality=95, subsampling=0)
                    elif suffix == ".webp":
                        canvas.save(output_temp, format="WEBP", quality=95)
                    else:
                        canvas.save(output_temp, format="PNG")
                    os.replace(output_temp, output)
                    created += 1
            except Exception as exc:
                errors.append(f"{source.name}: {exc}")
                output_temp.unlink(missing_ok=True)
    return destination, created, skipped, errors


def main():
    window = tk.Tk()
    window.title("BIGTITSLOVER963 | Watermark Studio")
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
    label(header, "◇  BIGTITSLOVER963", 11, ACCENT, True).pack(anchor="w")
    label(header, "Watermark Studio", 25, FG, True).pack(anchor="w", pady=(3, 0))
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

    settings = tk.Frame(controls, bg=CARD)
    settings.pack(fill="x", pady=(18, 0))
    left = tk.Frame(settings, bg=CARD)
    left.pack(side="left", anchor="n", fill="x", expand=True, padx=(0, 24))
    right = tk.Frame(settings, bg=CARD)
    right.pack(side="left", anchor="n", fill="x", expand=True)
    label(left, "03  /  WATERMARK SIZE", 10, ACCENT, True).pack(anchor="w")
    label(left, "Width as a percent of the image", 9, MUTED).pack(anchor="w", pady=(1, 5))
    width_var = tk.IntVar(value=25)
    ttk.Spinbox(left, from_=5, to=60, textvariable=width_var, width=7,
                style="Dark.TSpinbox").pack(anchor="w")
    label(right, "04  /  LETTERING COLOR", 10, ACCENT, True).pack(anchor="w")
    color_var = tk.StringVar(value="Original purple")
    selected_color = [None]
    color_row = tk.Frame(right, bg=CARD)
    color_row.pack(fill="x", pady=(7, 0))
    hue_var = tk.IntVar(value=278)
    swatch = tk.Label(color_row, width=3, bg="#7920ad", relief="solid", bd=1,
                      highlightbackground=ACCENT, highlightthickness=2)

    with Image.open(MARK) as graphic:
        base_mark = graphic.convert("RGBA")
        base_mark = base_mark.crop(base_mark.getbbox())

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
        mark = colored_watermark(base_mark, selected_color[0])
        try:
            width = min(60, max(5, width_var.get()))
        except tk.TclError:
            width = 25
        size = (max(1, round(700 * width / 100)), 0)
        size = (size[0], max(1, round(size[0] * mark.height / mark.width)))
        overlay = mark.resize(size, Image.Resampling.LANCZOS)
        backdrop.alpha_composite(overlay, (14, 150 - 14 - size[1]))
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
        try:
            width = width_var.get()
            if not 5 <= width <= 60:
                raise ValueError("Choose a watermark width between 5% and 60%.")
            destination, created, skipped, errors = process_folder(
                Path(folder_var.get()), width, selected_color[0], replace_var.get(), character_var.get())
        except Exception as exc:
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
    label(footer, "Bottom-left  ·  100% opacity  ·  Originals kept safe", 9, MUTED).pack(anchor="w", pady=(9, 0))
    width_var.trace_add("write", update_preview)
    window.after(0, update_preview)
    window.after(250, poll_updates)
    window.after(4000, check_updates)
    window.mainloop()


if __name__ == "__main__":
    main()
