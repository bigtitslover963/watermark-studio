"""Check trusted GitHub releases and replace a frozen Windows application."""
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import urllib.request


ROOT = Path(__file__).resolve().parent
APP_NAME = "Watermark Studio.exe"


def build_info():
    with (ROOT / "build_info.json").open(encoding="utf-8") as stream:
        return json.load(stream)


def version_tuple(version):
    value = version.lstrip("vV")
    parts = value.split(".")
    if len(parts) != 3 or any(not part.isdigit() for part in parts):
        raise ValueError("Releases must use version tags like v1.2.3")
    return tuple(map(int, parts))


def request(url):
    if not url.startswith("https://"):
        raise ValueError("Updates require HTTPS")
    return urllib.request.Request(url, headers={"User-Agent": "WatermarkStudio-Updater/1.0"})


def latest_release():
    info = build_info()
    repo = info.get("repository", "")
    if not getattr(sys, "frozen", False) or not repo or "/" not in repo:
        return None
    with urllib.request.urlopen(request(f"https://api.github.com/repos/{repo}/releases/latest"), timeout=12) as response:
        release = json.load(response)
    if version_tuple(release["tag_name"]) <= version_tuple(info["version"]):
        return None
    assets = {item["name"]: item["browser_download_url"] for item in release["assets"]}
    if APP_NAME not in assets or APP_NAME + ".sha256" not in assets:
        raise RuntimeError("The new release is still being built. Please check again in a minute.")
    exe_url = assets[APP_NAME]
    digest_url = assets[APP_NAME + ".sha256"]
    prefix = f"https://github.com/{repo}/releases/download/"
    if not exe_url.startswith(prefix) or not digest_url.startswith(prefix):
        raise ValueError("Unexpected update source")
    return release["tag_name"], exe_url, digest_url


def download_update(exe_url, digest_url):
    with urllib.request.urlopen(request(digest_url), timeout=30) as response:
        digest = response.read(512).decode("ascii").strip().split()[0].lower()
    if len(digest) != 64 or any(ch not in "0123456789abcdef" for ch in digest):
        raise ValueError("Release checksum is invalid")
    target_dir = Path(tempfile.mkdtemp(prefix="watermark-studio-update-"))
    staged = target_dir / APP_NAME
    checksum = hashlib.sha256()
    with urllib.request.urlopen(request(exe_url), timeout=60) as response, staged.open("wb") as output:
        total = 0
        while chunk := response.read(1024 * 1024):
            total += len(chunk)
            if total > 300 * 1024 * 1024:
                raise ValueError("Update exceeds the maximum allowed size")
            checksum.update(chunk)
            output.write(chunk)
    if checksum.hexdigest() != digest:
        staged.unlink(missing_ok=True)
        raise ValueError("Update checksum did not match")
    return staged


def install_after_exit(staged):
    if not getattr(sys, "frozen", False) or os.name != "nt":
        raise RuntimeError("Automatic installation only works in the Windows EXE")
    current = Path(sys.executable)
    if current.name.casefold() != APP_NAME.casefold():
        raise RuntimeError("The app was renamed; keep its original EXE filename for updates")
    script = staged.parent / "install-update.ps1"

    def quote(path):
        return "'" + str(path).replace("'", "''") + "'"

    script.write_text(
        f"Wait-Process -Id {os.getpid()} -ErrorAction SilentlyContinue\n"
        "$done = $false\n"
        "for ($i = 0; $i -lt 30; $i++) {\n"
        f"  try {{ Copy-Item -LiteralPath {quote(staged)} -Destination {quote(current)} -Force -ErrorAction Stop; $done = $true; break }} catch {{ Start-Sleep -Seconds 1 }}\n"
        "}\n"
        f"if ($done) {{ Start-Process -FilePath {quote(current)} }}\n",
        encoding="utf-8",
    )
    subprocess.Popen(["powershell.exe", "-NoProfile", "-ExecutionPolicy", "Bypass", "-File", str(script)],
                     creationflags=subprocess.CREATE_NO_WINDOW)
