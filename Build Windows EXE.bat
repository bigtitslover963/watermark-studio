@echo off
setlocal
cd /d "%~dp0"
title Build Watermark Studio EXE
echo Installing the Windows EXE builder and image library...
py -3.13 -m pip install --upgrade pyinstaller pillow
if errorlevel 1 goto failed

echo.
echo Building Watermark Studio.exe with your purple app icon...
py -3.13 -m PyInstaller --noconfirm --clean --onefile --windowed --name "Watermark Studio" --icon "WatermarkStudio.ico" --add-data "bigtitslover963.png:." --add-data "WatermarkStudio.ico:." --add-data "build_info.json:." --distpath dist --workpath build --specpath . watermark_tool.py
if errorlevel 1 goto failed

echo.
echo Finished! Your standalone app is in the dist folder:
echo %~dp0dist\Watermark Studio.exe
explorer "%~dp0dist"
pause
exit /b 0

:failed
echo.
echo The build did not finish. The error is above; please send a screenshot.
pause
exit /b 1
