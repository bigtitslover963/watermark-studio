@echo off
cd /d "%~dp0"
where py >nul 2>&1
if %errorlevel%==0 (
  py -3 -c "import PIL" >nul 2>&1 || py -3 -m pip install Pillow
  py -3 "%~dp0watermark_tool.py" "%~1"
) else (
  python -c "import PIL" >nul 2>&1 || python -m pip install Pillow
  python "%~dp0watermark_tool.py" "%~1"
)
if errorlevel 1 pause
