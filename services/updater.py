"""Servicio de actualización automática via GitHub Releases.

Arquitectura:
  1. CHECK  → GET api.github.com/.../releases/latest, compara tag con version local
  2. DOWNLOAD → Descarga .exe del release a carpeta temporal
  3. APPLY → Crea script .bat que espera a que el proceso termine,
             reemplaza el .exe y reinicia la app
"""

import json
import os
import subprocess
import sys
import time
import urllib.request
import aiohttp
from pathlib import Path
from typing import Optional

from utils.logger import logger

# ─── Configuración ──────────────────────────────────────────────
GITHUB_REPO = "juancito8812/botdetrading"
RELEASES_API = f"https://api.github.com/repos/{GITHUB_REPO}/releases/latest"
VERSION_FILE = "VERSION"
UPDATE_DIR = Path("updates")


# ─── Version helpers ────────────────────────────────────────────

def get_current_version() -> str:
    """Lee la versión actual desde el archivo VERSION."""
    try:
        vf = Path(VERSION_FILE)
        if vf.exists():
            return vf.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.debug(f"No se pudo leer VERSION: {e}")
    return "v0.0.0"


def parse_version(version_str: str) -> tuple:
    """Convierte 'v1.2.3' a tupla (1, 2, 3) para comparar.
    Siempre retorna una tupla de 3 elementos para evitar TypeError
    al comparar versiones de distinta longitud."""
    v = version_str.removeprefix("v").removeprefix("V")
    parts = v.split(".")
    try:
        parts_int = [int(p) for p in parts]
        while len(parts_int) < 3:
            parts_int.append(0)
        return tuple(parts_int[:3])
    except ValueError:
        return (0, 0, 0)


def is_newer_version(latest: str, current: str) -> bool:
    """Retorna True si latest > current."""
    return parse_version(latest) > parse_version(current)


# ─── API GitHub ─────────────────────────────────────────────────

# ─── Download ───────────────────────────────────────────────────

async def download_update(download_url: str, dest_dir: Path = UPDATE_DIR) -> Optional[Path]:
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        filename = download_url.rstrip("/").split("/")[-1] or "update.exe"
        dest_path = dest_dir / filename

        logger.info(f"Descargando actualización: {filename}")

        async with aiohttp.ClientSession() as session:
            async with session.get(download_url, headers={"User-Agent": "MiBotTrading/1.0"}) as resp:
                total = int(resp.headers.get("Content-Length", 0))
                downloaded = 0
                last_pct = -1
                with open(dest_path, "wb") as f:
                    async for chunk in resp.content.iter_chunked(8192):
                        if not chunk:
                            break
                        f.write(chunk)
                        downloaded += len(chunk)
                        if total > 0:
                            pct = downloaded * 100 // total
                            if pct != last_pct and pct % 25 == 0:
                                logger.info(f"  Progreso: {pct}%")
                                last_pct = pct

        size_mb = dest_path.stat().st_size / (1024 * 1024)
        logger.info(f"Descarga completada: {dest_path.name} ({size_mb:.1f} MB)")
        return dest_path
    except Exception as e:
        logger.error(f"Error descargando actualización: {e}")
        return None


# ─── Apply update ───────────────────────────────────────────────

def create_update_script(downloaded_path: Path) -> Optional[Path]:
    """Crea un script .bat que aplica la actualización.

    El script:
      1. Espera 3s a que el proceso padre termine
      2. Reemplaza el .exe (o extrae .zip y copia)
      3. Inicia el nuevo .exe
      4. Se autoelimina

    Retorna la ruta del script o None.
    """
    if not getattr(sys, "frozen", False):
        logger.error("No se puede actualizar en modo desarrollo (script Python)")
        return None

    current_exe = Path(sys.executable).resolve()
    script_path = UPDATE_DIR / "apply_update.bat"
    UPDATE_DIR.mkdir(parents=True, exist_ok=True)

    is_zip = str(downloaded_path).lower().endswith(".zip")

    lines = [
        "@echo off",
        "chcp 65001 >nul 2>&1",
        "title Aplicando actualización MiBotTrading...",
        "",
        "echo Esperando a que el bot se cierre...",
        "timeout /t 3 /nobreak >nul",
        "",
        "echo Aplicando actualización...",
    ]

    if is_zip:
        lines.extend([
            f'set ZIP_FILE="{downloaded_path}"',
            f'set EXE_PATH="{current_exe}"',
            'set TMP_DIR="%TEMP%\\mi_bot_update_%RANDOM%"',
            'mkdir "%TMP_DIR%"',
            'echo Extrayendo archivos...',
            'powershell -command "Expand-Archive -Path %ZIP_FILE% -DestinationPath %TMP_DIR% -Force" >nul 2>&1',
            'echo Buscando .exe en la extracción...',
            'for /r "%TMP_DIR%" %%f in (*.exe) do (',
            '    echo Copiando nuevo ejecutable...',
            '    copy /y "%%f" %EXE_PATH% >nul',
            '    if errorlevel 1 (',
            '        echo ERROR: No se pudo copiar el archivo.',
            '        pause',
            '        exit /b 1',
            '    )',
            '    goto :launch',
            ')',
            'echo ERROR: No se encontro ningun .exe en la actualizacion.',
            'pause',
            'exit /b 1',
        ])
    else:
        lines.extend([
            f'copy /y "{downloaded_path}" "{current_exe}" >nul',
            'if errorlevel 1 (',
            '    echo ERROR: No se pudo copiar el archivo.',
            '    echo Puede que el bot siga en ejecucion.',
            '    pause',
            '    exit /b 1',
            ')',
        ])

    lines.extend([
        "",
        ":launch",
        f'echo Iniciando {current_exe.name}...',
        f'start "" "{current_exe}"',
        "",
        "echo Limpiando archivos temporales...",
        f'del /f /q "{script_path}" >nul 2>&1',
        "exit",
    ])

    script_path.write_text("\r\n".join(lines), encoding="utf-8")
    logger.info(f"📝 Script de actualización creado: {script_path}")
    return script_path


def apply_update(downloaded_path: Path) -> bool:
    """Aplica la actualización y cierra la app.

    Retorna True si se inició el proceso de actualización.
    """
    script = create_update_script(downloaded_path)
    if not script:
        return False

    logger.info("🔄 Iniciando actualización...")
    try:
        subprocess.Popen(
            ["cmd.exe", "/c", "start", "", str(script)],
            shell=False,
            creationflags=subprocess.CREATE_NEW_CONSOLE if hasattr(subprocess, "CREATE_NEW_CONSOLE") else 0,
        )
        return True
    except Exception as e:
        logger.error(f"Error ejecutando script de actualización: {e}")
        return False


# ─── Sync convenience ──────────────────────────────────────────

_last_check = 0.0
_last_result = None

def check_latest_version() -> Optional[dict]:
    global _last_check, _last_result
    if time.time() - _last_check < 300:
        return _last_result
    try:
        req = urllib.request.Request(
            RELEASES_API,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "MiBotTrading/1.0",
            },
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())

        assets = data.get("assets", [])
        download_url = ""
        for asset in assets:
            name = asset.get("name", "").lower()
            if name.endswith(".exe"):
                download_url = asset.get("browser_download_url", "")
                break
            if not download_url and name.endswith(".zip"):
                download_url = asset.get("browser_download_url", "")

        _last_check = time.time()
        _last_result = {
            "tag_name": data.get("tag_name", "v0.0.0"),
            "download_url": download_url,
            "body": data.get("body", ""),
        }
        return _last_result
    except Exception as e:
        logger.warning(f"Error checking for updates: {e}")
        return None
