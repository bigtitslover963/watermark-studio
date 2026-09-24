BIGTITSLOVER963 Batch Watermark Tool (Windows)

The interface uses a neon purple dashboard style with a live grid preview.
The Create button stays at the bottom; scroll the settings if your screen is
small or Windows display scaling makes them taller than the window.

1. Extract the entire ZIP to a folder.
2. Install Python 3 from python.org if it is not installed. During setup,
   enable "Add Python to PATH". Internet access is needed the first time
   the launcher installs Pillow.
3. Double-click "Start Watermark Tool.bat". Choose a folder with your images,
   then click "Create watermarked copies". You can also drag an image folder
   onto the .bat file to fill in the folder automatically.

TO CREATE A STANDALONE WINDOWS EXE WITH THE PURPLE APP ICON:
Double-click "Build Windows EXE.bat" on your Windows PC. It installs PyInstaller
and builds "dist\Watermark Studio.exe". Python and internet access are needed
to build it once; the resulting .exe runs without Python installed and includes
the watermark PNG and WatermarkStudio.ico inside it. The .exe can be moved out
of the dist folder. Keep the .ico file if you want to change a shortcut icon
manually in Windows.

AUTOMATIC UPDATES (GITHUB RELEASE BUILD):
The repo includes .github/workflows/release.yml. Put the contents of this
folder at the ROOT of your new GitHub repository. Push a version tag such as
v1.0.0 to build and publish the first Windows EXE and its SHA256 checksum.
Download that first EXE once. Thereafter it checks the repository's latest
release when it opens and offers to download/install a newer version. You can
also click CHECK FOR UPDATES. The update is checked against its SHA256 file.
Future versions need a new version tag, such as v1.0.1, after code changes.
The locally built EXE has no repository address and cannot auto-update;
automatic updates are enabled in EXEs built by the GitHub release workflow.

The graphic is applied at full opacity in the bottom-left, with a 2% margin.
Its width defaults to 25% of each image's width; change the percentage in the
window if desired. Move the color slider to change the hue, use "Choose exact
color" for a specific shade, or press "Original purple" to restore the PNG's
original color. The lettering shape and transparent edges are preserved.
The preview updates as you change the size or color.
Images may be PNG, JPG, JPEG, or WebP. New copies go into
the selected folder's Watermarked subfolder, with _watermarked added to each
filename. Originals are never changed. Existing watermarked copies are skipped
so running the program twice will not overwrite earlier results. To change the
color or size of earlier copies, check "Replace existing watermarked copies"
before running the tool again. Only files in Watermarked are replaced.

If you enter a character name, images are numbered in filename order (1, 2, 3,
and so on). The tool creates clean copies in "Named Originals" such as
"Rias Gremory 1.png" and watermarked copies in "Watermarked" such as
"Rias Gremory 1b.png". The files in the selected image folder stay untouched.
Keep the input images together between runs so their numbers remain consistent.
Leave the character field blank for the original _watermarked naming pattern.
When the batch finishes, the results window shows created, skipped, and failed
counts and has a button to open the Watermarked folder.

Keep bigtitslover963.png in the same folder as watermark_tool.py.
