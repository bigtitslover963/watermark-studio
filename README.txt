WATERMARK STUDIO - QUICK START (WINDOWS)

Download "Watermark Studio.exe" from the latest GitHub release under Assets:
https://github.com/bigtitslover963/watermark-studio/releases/latest
Double-click the EXE. Python is not needed for the release EXE.

1. Click Browse and select the folder containing your PNG, JPG, JPEG, WebP,
   GIF or MP4 files.
2. Type your own text in WATERMARK TEXT. The app does not fill in a name.
3. Choose a font, color, size, position and opacity. Check LIVE PREVIEW.
4. Optionally enter a CHARACTER NAME for numbered filenames.
5. Scroll to CREATE WATERMARKED COPIES and click it.

Source images are untouched. New copies go into a Watermarked folder. A
character name also creates clean numbered copies in Named Originals:
"Rias Gremory 1.png" and "Rias Gremory 1b.png" (watermarked), then 2, 3, etc.
Without a character name, "photo.png" becomes "photo_watermarked.png".

Existing watermarked files are skipped unless you check "Replace existing
watermarked copies". Save and Load presets to reuse text and appearance.
Use CHECK FOR UPDATES in the release EXE to install future versions.

The progress bar tracks your batch. Click CANCEL to stop and keep completed
copies. Incomplete outputs are removed. GIF timing and loops are preserved;
MP4 audio is kept. FFmpeg is included in the release EXE. Large GIFs may need
resizing or shortening: width x height x frame count must be <= 50 million.

For a full guide, see README.md in the repository. If building from source,
install Python 3.13 and run "Build Windows EXE.bat". A locally built EXE does
not have automatic updates.
