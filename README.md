# Watermark Studio

A Windows batch image watermark app with a purple interface and live preview. Your source images stay untouched.

## Download and start

1. On the [latest release](https://github.com/bigtitslover963/watermark-studio/releases/latest), expand **Assets** and download **Watermark Studio.exe**. The **Source code** ZIP is not the Windows app.
2. Put the EXE in a folder where you want to keep it and double-click it. Python is not required. Keep its filename as **Watermark Studio.exe** for automatic updates.
3. When a newer version is available, the app offers to install it. You can also click **CHECK FOR UPDATES** at the bottom.

## Watermark your images

1. Put your PNG, JPG, JPEG, WebP, GIF, or MP4 files together in one folder. In **01 / IMAGE FOLDER**, click **Browse** and select that folder.
2. In **03 / WATERMARK TEXT**, type the text you want on the images. This field is required; no DA name is filled in automatically.
3. Pick a font and check the **LIVE PREVIEW**. Optionally use **Import font** for a `.ttf`, `.otf`, or `.ttc` file.
4. Adjust **WATERMARK SIZE** (25% by default), **LETTERING COLOR**, **POSITION** (bottom left by default), and **OPACITY** (100% by default). Size is the watermark width as a percentage of each image's width.
5. Optionally type a **CHARACTER NAME** to number the output files. Then scroll down and click **CREATE WATERMARKED COPIES**.

Your input images stay untouched. Without a character name, `photo.png` creates `Watermarked/photo_watermarked.png`. With `Rias Gremory` as the name, the app creates `Named Originals/Rias Gremory 1.png` and `Watermarked/Rias Gremory 1b.png`, followed by 2, 3, and so on in filename order. The named original is a copy.

Existing watermarked files are skipped. To apply changed settings to the same output filenames, check **Replace existing watermarked copies** and run the batch again. The finished popup shows created, skipped, and failed counts and has a button to open the output folder.

## GIFs, videos, and cancellation

GIFs keep their frame timing and looping. MP4 videos are re-encoded with the watermark and keep their audio tracks. The release EXE includes FFmpeg, so you do not need to install it separately. The EXE is larger than previous releases because it includes video processing.

The progress bar shows overall batch progress; the status line shows the current file and its progress. Click **CANCEL** to stop. Completed copies remain, and unfinished output files are removed. If replacing an existing output, cancelling keeps the previous copy. GIF encoding and still-image saving may finish their current step before cancellation is acknowledged. Closing the window during a batch also cancels it safely.

To limit memory usage, GIFs are limited to 50 million pixels across all frames (width × height × frame count). Videos are limited to 40 megapixels per frame. Very large GIFs should be resized or shortened first. GIF colors may be adjusted to fit the format's 256-color palette.

## Fonts and presets

**Import font** copies a font into `%LOCALAPPDATA%\WatermarkStudio\fonts`, so it remains available after you close the app. Only import fonts you have permission to use.

To reuse settings, type a name in **SAVED PRESETS** and click **Save**. Choose that name and click **Load** to restore the text, font, color, size, position, and opacity, or **Delete** to remove it. The image folder and character name are chosen separately for each batch. Presets are stored in `%LOCALAPPDATA%\WatermarkStudio\presets.json`. Older presets that only used the removed original-logo option need watermark text before they can be used.

## Build on Windows

If you want to build it yourself, install Python 3.13 and run **Build Windows EXE.bat**. The resulting app is `dist/Watermark Studio.exe`.

## Releases and updates

A version tag triggers `.github/workflows/release.yml` to publish a Windows EXE and its SHA256 checksum. The release EXE checks GitHub for updates and verifies the download against the published checksum before installing. The locally built EXE does not know a repository address and therefore does not auto-update. The GitHub repository must be public for update checks without signing in.
