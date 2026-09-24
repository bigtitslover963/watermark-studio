# Watermark Studio

A Windows batch image watermark app with a purple interface, live preview, and numbered clean/watermarked pairs. Originals in the selected folder are left untouched.

Enter text in **Watermark text** to make your own lettering and choose a font installed on your PC. The live preview shows your font and chosen color. Leave the field blank to use the original BIGTITSLOVER963 graphic. The watermark width defaults to 25% of each image.

Use **Import font** to choose a `.ttf`, `.otf`, or `.ttc` file without installing it in Windows. The app saves a copy in `%LOCALAPPDATA%\WatermarkStudio\fonts` so it stays in the picker after you reopen it. Only import fonts you have permission to use.

Choose one of nine watermark positions, set opacity from 0 to 100%, and save your watermark text, font, color, width, position, and opacity as a named preset. Use **Load** to restore it later or **Delete** to remove it. Presets are stored in `%LOCALAPPDATA%\WatermarkStudio\presets.json`. The image folder and character filename are selected separately for each batch.

## Build on Windows

Install Python 3.13, then run **Build Windows EXE.bat**. The resulting app is `dist/Watermark Studio.exe`.

## Releases and updates

A new tag such as `v1.0.0` triggers `.github/workflows/release.yml` to publish a Windows EXE and its SHA256 checksum. The release build embeds the repository address and version. It checks for newer GitHub Releases when opened, asks before installing, and verifies the downloaded EXE against the published checksum.

Use a public repository for unauthenticated update checks. The locally built EXE does not know a repository address and therefore does not auto-update.
