# Watermark Studio

A Windows batch image watermark app with a purple interface, live preview, and numbered clean/watermarked pairs. Originals in the selected folder are left untouched.

## Build on Windows

Install Python 3.13, then run **Build Windows EXE.bat**. The resulting app is `dist/Watermark Studio.exe`.

## Releases and updates

A new tag such as `v1.0.0` triggers `.github/workflows/release.yml` to publish a Windows EXE and its SHA256 checksum. The release build embeds the repository address and version. It checks for newer GitHub Releases when opened, asks before installing, and verifies the downloaded EXE against the published checksum.

Use a public repository for unauthenticated update checks. The locally built EXE does not know a repository address and therefore does not auto-update.
