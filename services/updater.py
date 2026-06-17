from pathlib import Path
from typing import Optional
from utils.logger import logger

VERSION_FILE = "VERSION"

def get_current_version() -> str:
    try:
        vf = Path(VERSION_FILE)
        if vf.exists():
            return vf.read_text(encoding="utf-8").strip()
    except Exception as e:
        logger.debug(f"No se pudo leer VERSION: {e}")
    return "v0.0.0"

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

def check_latest_version() -> Optional[dict]:
    return {"tag_name": get_current_version(), "download_url": "", "body": ""}

async def download_update(download_url: str, dest_dir=None) -> Optional[Path]:
    return None

def apply_update(downloaded_path) -> bool:
    return False
