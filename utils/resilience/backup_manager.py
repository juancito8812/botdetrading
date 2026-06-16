"""Backup automático rotativo de archivos críticos."""

import gzip
import json
import logging
import os
import shutil
from datetime import datetime
from typing import List, Optional

logger = logging.getLogger("TradingBot")


class BackupManager:
    """
    Gestiona backups automáticos rotativos de archivos críticos.

    Los backups se guardan comprimidos con gzip y se rotan
    cuando se excede el número máximo configurado.
    """

    def __init__(
        self,
        backup_dir: str,
        max_backups: int = 24,
        interval_minutes: int = 15,
    ):
        self.backup_dir = backup_dir
        self.max_backups = max_backups
        self.interval_minutes = interval_minutes

        os.makedirs(backup_dir, exist_ok=True)

    def create_backup(self, source_path: str, name: str) -> Optional[str]:
        """
        Crea un backup comprimido del archivo source.

        Args:
            source_path: Ruta al archivo a respaldar
            name: Nombre identificador (ej: "posiciones", "config")

        Returns:
            Ruta al archivo de backup, o None si falló.
        """
        if not os.path.exists(source_path):
            logger.warning(f"Backup: {source_path} no existe, saltando")
            return None

        try:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            backup_name = f"{name}_{timestamp}.json.gz"
            backup_path = os.path.join(self.backup_dir, backup_name)

            with open(source_path, "rb") as f_in:
                with gzip.open(backup_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)

            logger.debug(f"💾 Backup creado: {backup_path}")
            self._rotate(name)
            return backup_path

        except Exception as e:
            logger.error(f"Error creando backup de {source_path}: {e}")
            return None

    def _rotate(self, name: str):
        """Elimina los backups más antiguos si se excede el máximo."""
        backups = self._list_backups(name)
        while len(backups) > self.max_backups:
            oldest = backups[0]
            try:
                os.remove(oldest)
            except Exception as e:
                logger.warning(f"Error rotando backup {oldest}: {e}")
                backups.pop(0)
                continue
            backups.pop(0)
            logger.debug(f"🗑️ Backup rotado: {oldest}")

    def _list_backups(self, name: str) -> List[str]:
        """Lista los backups de un tipo, ordenados por fecha (más antiguos primeros)."""
        pattern = f"{name}_"
        backups = []
        for f in os.listdir(self.backup_dir):
            if f.startswith(pattern) and f.endswith(".json.gz"):
                full_path = os.path.join(self.backup_dir, f)
                backups.append(full_path)

        def _safe_getmtime(path):
            try:
                return os.path.getmtime(path)
            except OSError:
                return 0

        backups.sort(key=_safe_getmtime)
        return backups

    def restore_latest(self, target_path: str, name: str) -> bool:
        """
        Restaura el backup más reciente al target_path.

        Args:
            target_path: Ruta donde restaurar el archivo
            name: Nombre identificador del backup

        Returns:
            True si se restauró correctamente, False si no.
        """
        backups = self._list_backups(name)
        if not backups:
            logger.warning(f"No hay backups de {name} para restaurar")
            return False

        latest = backups[-1]
        try:
            with gzip.open(latest, "rb") as f_in:
                with open(target_path, "wb") as f_out:
                    shutil.copyfileobj(f_in, f_out)
            logger.info(f"♻️ Backup restaurado: {latest} → {target_path}")
            return True
        except Exception as e:
            logger.error(f"Error restaurando backup {latest}: {e}")
            return False
