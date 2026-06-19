"""
Auto-updater: consulta GitHub Releases, descarga y aplica actualizaciones.

Flujo:
  1. check_latest_version() → consulta API de GitHub, retorna info de la última release
  2. download_update(url) → descarga MiBotTrading.exe
  3. apply_update(path) → crea .bat que reemplaza el .exe y reinicia

Todas las funciones son síncronas (usadas desde threads en la UI).
"""
import json
import os
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

from utils.helpers import BASE_DIR
from utils.logger import logger

VERSION_FILE = "VERSION"
# Versión por defecto (fallback cuando VERSION no existe, ej: en otra PC sin el archivo)
_CURRENT_VERSION = "v2.1.0"
_GITHUB_API = "https://api.github.com/repos/juancito8812/botdetrading/releases/latest"
_ASSET_NAME = "MiBotTrading.exe"


def get_current_version() -> str:
    """
    Lee la versión actual desde el archivo VERSION.
    Fallback a _CURRENT_VERSION si el archivo no existe.
    """
    try:
        vf = Path(VERSION_FILE)
        if not vf.exists():
            vf = BASE_DIR / VERSION_FILE
        if vf.exists():
            return vf.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.debug(f"No se pudo leer VERSION: {e}")
    return _CURRENT_VERSION


def parse_version(version_str: str) -> tuple:
    """Convierte 'v2.0.1' → (2, 0, 1)."""
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
    """True si latest > current."""
    return parse_version(latest) > parse_version(current)


def check_latest_version() -> Optional[dict]:
    """
    Consulta GitHub Releases API y retorna info de la última versión.

    Retorna dict con:
      - tag_name: str (ej: "v2.0.1")
      - download_url: str (URL directa del .exe)
      - body: str (release notes)

    Retorna None si hay error (red, rate limit, etc.).
    """
    try:
        req = urllib.request.Request(
            _GITHUB_API,
            headers={
                "Accept": "application/vnd.github.v3+json",
                "User-Agent": "MiBotTrading/2.0",
            },
        )
        with urllib.request.urlopen(req, timeout=15) as resp:
            if resp.status != 200:
                logger.warning(f"GitHub API respondió {resp.status}")
                return None
            data = json.loads(resp.read().decode("utf-8"))

        tag_name = data.get("tag_name", "")
        body = data.get("body", "")

        # Buscar el asset .exe
        download_url = ""
        assets = data.get("assets", [])
        for asset in assets:
            if asset.get("name", "").lower() == _ASSET_NAME.lower():
                download_url = asset.get("browser_download_url", "")
                break

        if not tag_name:
            logger.warning("GitHub API no devolvió tag_name")
            return None

        logger.info(f"📡 Última versión en GitHub: {tag_name}")
        return {"tag_name": tag_name, "download_url": download_url, "body": body}

    except urllib.error.HTTPError as e:
        logger.warning(f"GitHub API HTTP {e.code}: {e.reason}")
        return None
    except urllib.error.URLError as e:
        logger.warning(f"Error de red consultando GitHub: {e.reason}")
        return None
    except Exception as e:
        logger.warning(f"Error inesperado en check_latest_version: {e}")
        return None


def download_update(download_url: str, dest_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Descarga MiBotTrading.exe desde la URL de GitHub.

    Args:
        download_url: URL directa del asset.
        dest_dir: Directorio destino (por defecto BASE_DIR).

    Returns:
        Path al archivo descargado, o None si falla.
    """
    if not download_url:
        logger.error("URL de descarga vacía")
        return None

    dest = (dest_dir or BASE_DIR) / "MiBotTrading_new.exe"
    logger.info(f"⬇️ Descargando update desde {download_url}")

    try:
        with urllib.request.urlopen(download_url, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded = 0
            chunk_size = 8192
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded += len(chunk)
                    if total > 0 and downloaded % (chunk_size * 100) == 0:
                        pct = downloaded / total * 100
                        logger.info(f"⬇️  Descargando... {pct:.0f}% ({downloaded // 1024 // 1024} MB)")

        size_mb = dest.stat().st_size / (1024 * 1024)
        logger.info(f"✅ Update descargado: {size_mb:.0f} MB → {dest}")
        return dest

    except urllib.error.HTTPError as e:
        logger.error(f"Error HTTP descargando: {e.code} {e.reason}")
        _cleanup_temp(dest)
        return None
    except urllib.error.URLError as e:
        logger.error(f"Error de red descargando: {e.reason}")
        _cleanup_temp(dest)
        return None
    except Exception as e:
        logger.error(f"Error inesperado descargando: {e}")
        _cleanup_temp(dest)
        return None


def _cleanup_temp(path: Path):
    """Elimina archivo temporal si existe."""
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def apply_update(downloaded_path: Path) -> bool:
    """
    Aplica la actualización: crea un script .bat que reemplaza el .exe y reinicia.

    El .bat:
      1. Espera a que el proceso actual termine
      2. Reemplaza MiBotTrading.exe con MiBotTrading_new.exe
      3. Elimina MiBotTrading_new.exe
      4. Reinicia MiBotTrading.exe

    Args:
        downloaded_path: Path al archivo descargado (MiBotTrading_new.exe).

    Returns:
        True si se lanzó el .bat correctamente.
    """
    downloaded = Path(downloaded_path)
    if not downloaded.exists():
        logger.error(f"Archivo descargado no encontrado: {downloaded}")
        return False

    if not getattr(sys, 'frozen', False):
        logger.info("Modo script: la actualización requiere ejecutar manualmente")
        return False

    exe_path = Path(sys.executable)
    exe_dir = exe_path.parent
    exe_name = exe_path.name
    new_exe = exe_dir / "MiBotTrading_new.exe"
    bat_path = exe_dir / "_update.bat"

    # Mover el descargado junto al .exe si no está ya ahí
    if downloaded.parent != exe_dir:
        import shutil
        shutil.move(str(downloaded), str(new_exe))

    bat_content = f"""@echo off
chcp 65001 >nul
title Actualizando MiBotTrading...
echo Esperando a que el bot termine...
:loop
tasklist /fi "IMAGENAME eq {exe_name}" 2>nul | find /i "{exe_name}" >nul
if not errorlevel 1 (
    timeout /t 2 /nobreak >nul
    goto loop
)
echo Reemplazando ejecutable...
move /y "{new_exe}" "{exe_path}" >nul
echo Iniciando nueva version...
start "" "{exe_path}"
del "%~f0"
"""
    try:
        bat_path.write_text(bat_content, encoding="utf-8")
        logger.info(f"📝 Script de actualización creado: {bat_path}")
        os.startfile(str(bat_path))
        logger.info("🚀 Script de actualización lanzado, cerrando bot...")
        return True
    except Exception as e:
        logger.error(f"Error creando script de actualización: {e}")
        return False
