"""
Auto-updater: consulta GitHub Releases, descarga y aplica actualizaciones.

Flujo:
  1. check_latest_version() → consulta GitHub (gh CLI o API), retorna info de la última release
  2. download_update(url, tag_name) → descarga MiBotTrading.exe
  3. apply_update(path) → crea .bat que reemplaza el .exe y reinicia

Todas las funciones son síncronas (usadas desde threads en la UI).

REPO PRIVADO: Si el repo es privado, la API HTTP devuelve 404.
  Se usa `gh release view` y `gh release download` como alternativa autenticada.
"""
import json
import subprocess
import sys
import urllib.request
import urllib.error
from pathlib import Path
from typing import Optional

from utils.helpers import BASE_DIR
from utils.logger import logger

VERSION_FILE = "VERSION"
_CURRENT_VERSION = "v2.1.8"
_GITHUB_API = "https://api.github.com/repos/juancito8812/botdetrading/releases/latest"
_GITHUB_RELEASES = "https://github.com/juancito8812/botdetrading/releases/latest"
_ASSET_NAME = "MiBotTrading.exe"
_CACHE_TTL = 300  # 5 min cache para no exceder rate limit de GitHub (60 req/hora sin auth)


def get_current_version() -> str:
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
    return parse_version(latest) > parse_version(current)


def _gh_release_view() -> Optional[dict]:
    """Usa gh CLI para obtener la última release (funciona con repos privados)."""
    try:
        r = subprocess.run(
            ['gh', 'release', 'view', '--json', 'tagName,assets,body'],
            capture_output=True, text=True, timeout=15
        )
        if r.returncode != 0:
            logger.debug(f"gh CLI no disponible: {r.stderr[:100]}")
            return None

        data = json.loads(r.stdout)
        tag_name = data.get("tagName", "")
        body = data.get("body", "")
        download_url = ""
        for asset in data.get("assets", []):
            if asset.get("name", "").lower() == _ASSET_NAME.lower():
                download_url = asset.get("browser_download_url", "")
                break

        if not tag_name:
            return None
        logger.info(f"📡 Última versión (gh): {tag_name}")
        return {"tag_name": tag_name, "download_url": download_url, "body": body}
    except (FileNotFoundError, subprocess.TimeoutExpired, json.JSONDecodeError) as e:
        logger.debug(f"gh CLI falló: {e}")
        return None


def _http_release_view() -> Optional[dict]:
    """Usa la API HTTP de GitHub (solo funciona con repos públicos)."""
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
        download_url = ""
        for asset in data.get("assets", []):
            if asset.get("name", "").lower() == _ASSET_NAME.lower():
                download_url = asset.get("browser_download_url", "")
                break

        if not tag_name:
            logger.warning("GitHub API no devolvió tag_name")
            return None
        logger.info(f"📡 Última versión en GitHub: {tag_name}")
        return {"tag_name": tag_name, "download_url": download_url, "body": body}
    except urllib.error.HTTPError as e:
        logger.warning(f"GitHub API HTTP {e.code}: {e.reason} (repo privado?)")
        return None
    except urllib.error.URLError as e:
        logger.warning(f"Error de red consultando GitHub: {e.reason}")
        return None
    except Exception as e:
        logger.warning(f"Error inesperado en check_latest_version: {e}")
        return None


# Cache simple para evitar exceder rate limit de GitHub
_cache_result = None
_cache_time = 0.0


def check_latest_version() -> Optional[dict]:
    """
    Consulta GitHub y retorna info de la última versión.
    Cachea el resultado por {_CACHE_TTL}s para no exceder rate limits.

    Prioridad:
      1. gh CLI (autenticado, funciona con repos privados)
      2. HTTP API (solo repos públicos)

    Retorna dict con:
      - tag_name: str (ej: \"v2.1.1\")
      - download_url: str (URL directa del .exe)
      - body: str (release notes)

    Retorna None si hay error.
    """
    import time
    global _cache_result, _cache_time

    now = time.time()
    if _cache_result and (now - _cache_time) < _CACHE_TTL:
        logger.debug("Usando versión cacheadas (TTL %ds)", _CACHE_TTL)
        return _cache_result

    info = _gh_release_view()
    if not info:
        info = _http_release_view()

    if info:
        _cache_result = info
        _cache_time = now
    return info


def _gh_download_asset(tag_name: str, dest_dir: Path) -> Optional[Path]:
    """Descarga el .exe usando gh CLI (funciona con repos privados)."""
    import tempfile
    import shutil
    tmp_dir = tempfile.mkdtemp(prefix="mibot_update_")
    try:
        logger.info(f"⬇️ Descargando con gh release download {tag_name}...")
        r = subprocess.run(
            ['gh', 'release', 'download', tag_name,
             '-p', _ASSET_NAME,
             '-D', tmp_dir],
            capture_output=True, text=True, timeout=300
        )
        if r.returncode != 0:
            logger.warning(f"gh download falló: {r.stderr[:200]}")
            return None

        downloaded = Path(tmp_dir) / _ASSET_NAME
        if downloaded.exists():
            size_mb = downloaded.stat().st_size / (1024 * 1024)
            logger.info(f"✅ Update descargado (gh): {size_mb:.0f} MB")
            new_name = dest_dir / "MiBotTrading_new.exe"
            if new_name.exists():
                new_name.unlink()
            shutil.move(str(downloaded), str(new_name))
            return new_name
        return None
    except (FileNotFoundError, subprocess.TimeoutExpired) as e:
        logger.warning(f"gh download no disponible: {e}")
        return None
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)


def _http_download_asset(download_url: str, dest_dir: Path) -> Optional[Path]:
    """Descarga el .exe vía HTTP (solo funciona con repos públicos)."""
    if not download_url:
        return None
    dest = dest_dir / "MiBotTrading_new.exe"
    try:
        with urllib.request.urlopen(download_url, timeout=120) as resp:
            total = int(resp.headers.get("Content-Length", 0))
            downloaded_bytes = 0
            chunk_size = 8192
            with open(dest, "wb") as f:
                while True:
                    chunk = resp.read(chunk_size)
                    if not chunk:
                        break
                    f.write(chunk)
                    downloaded_bytes += len(chunk)
                    if total > 0 and downloaded_bytes % (chunk_size * 100) == 0:
                        pct = downloaded_bytes / total * 100
                        logger.info(f"⬇️  Descargando... {pct:.0f}% ({downloaded_bytes // 1024 // 1024} MB)")

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


def download_update(download_url: str, tag_name: Optional[str] = None,
                    dest_dir: Optional[Path] = None) -> Optional[Path]:
    """
    Descarga MiBotTrading.exe desde GitHub.

    Args:
        download_url: URL directa del asset (fallback HTTP).
        tag_name: Nombre del tag (ej: \"v2.1.1\") para gh CLI download.
        dest_dir: Directorio destino (por defecto BASE_DIR).

    Returns:
        Path al archivo descargado, o None si falla.
    """
    dest = dest_dir or BASE_DIR

    # 1. Intentar con gh CLI (funciona con privados)
    if tag_name:
        result = _gh_download_asset(tag_name, dest)
        if result:
            return result

    # 2. Fallback HTTP (públicos)
    if download_url:
        result = _http_download_asset(download_url, dest)
        if result:
            return result

    logger.error("No se pudo descargar la actualización por ningún método")
    return None


def _cleanup_temp(path: Path):
    try:
        if path.exists():
            path.unlink()
    except Exception:
        pass


def get_releases_url() -> str:
    """Retorna la URL de la página de releases en GitHub."""
    return _GITHUB_RELEASES


def apply_update(downloaded_path: Path) -> bool:
    """
    Prepara la actualización: renombra el .exe descargado a .update.

    Ya no crea scripts (Windows Defender los bloquea).
    El usuario debe cerrar el bot, reemplazar manualmente y reiniciar.
    """
    downloaded = Path(downloaded_path)
    if not downloaded.exists():
        logger.error(f"Archivo descargado no encontrado: {downloaded}")
        return False

    exe_dir = downloaded.parent
    update_file = exe_dir / "MiBotTrading.exe.update"

    try:
        # Renombrar a .update para que Windows no lo marque como ejecutable
        if update_file.exists():
            update_file.unlink()
        import shutil
        shutil.move(str(downloaded), str(update_file))
        logger.info(f"📦 Update preparado: {update_file}")
        logger.info("ℹ️  Cierra el bot, reemplaza MiBotTrading.exe por MiBotTrading.exe.update y reinicia")
        return True
    except Exception as e:
        logger.error(f"Error preparando actualización: {e}")
        return False
